/**
 * Static-Contract CF 站点线 Worker —— static.mango-mesa.ccwu.cc 的服务端。
 *
 * 2026-11-06 收编进本仓（用户裁定）：此前它的源码寄生在课程站仓
 * （S26-1_202609）的 gitignored 目录里、以「userscript 宿主 + 附加路由」的
 * 形态存在；现在它是本仓管线的一等公民，与 deploy-eo/deploy-cf 两条
 * 站点分支同属一个产地。收编时按用户裁定**不带**旧 userscript 三路由
 * （/assistant.user.js 等）——那条线已停止维护。
 *
 * 三段职责，一图流：
 *
 *   OPTIONS                        → 204 + CORS 预检头
 *   /<o>/<r>/releases/download/... → GitHub release 字节代理（fetch 默认
 *                                    redirect: follow，边缘替客户端跟完
 *                                    GitHub 的 302 → release-assets 两跳）
 *   其余路径                        → 站点产物运行期回源 raw deploy-cf 分支
 *
 * 为什么站点产物**运行期回源**而不内联（2026-11-01 事故为证）：内联是打包
 * 快照，只有重新部署才会变；而产物产地是本仓的 deploy-cf 分支（sync-deploy
 * 派生）。运行期回源让「deploy-cf 分支 = 唯一产地」成立，发布即刻可见，
 * 不需要任何人跨仓重新部署。代价是冷请求多一跳（raw 自带 max-age=300，
 * Worker 侧 edge cache 再叠一层，实际回源很少）。
 *
 * ★ 响应头三件套（ACAO / CORP / nosniff）在**所有资源响应**上统一注入：
 *   消费端（Octave-UI）跑在 COEP require-corp 的跨源隔离上下文里，
 *   缺 CORP 时浏览器直接拦掉——curl 全 200、浏览器全 ERR_FAILED（其 003 信）。
 *   raw.githubusercontent.com 自带这两个头，所以 EO 主线只在 release 路径
 *   需要补；本 Worker 的所有响应都自己生成，一律带全。
 */

// deploy-cf 的 catalogue.base 指向本 Worker 的域（用户裁定 2026-11-04：
// 一个镜像源 = 一个 deploy 分支，读者从哪条线拿 catalogue 就近走哪条线）
const SITE_UPSTREAM =
	"https://raw.githubusercontent.com/ArchivalEra/Static-Contract/deploy-cf";

// 回源路径白名单：只允许这些扩展名（防「任意路径不管什么都回源」变开放代理）
const SITE_ALLOWED_EXT = new Set([
	".html",
	".json",
	".md",
	".py",
	".svg",
	".png",
	".txt",
]);

// 无扩展名的产物名。`LICENSE` 这类合规文件天生没有后缀 —— 纯扩展名
// 白名单会把它挡成 404（对方 `009` 抓到的死链）。
// 只放行**顶层单段**的无扩展名文件，且上游前缀固定在本仓 deploy-cf
// 分支，所以没有借道当开放代理的空间。
const SITE_BARE_NAMES = new Set(["LICENSE", "NOTICE", "COPYING", "AUTHORS"]);

/**
 * 扩展名 → Content-Type。回源拿到的是 raw（Content-Type: text/plain），
 * 类型由这里按扩展名决定，不信任上游。
 */
const TYPES = {
	".html": "text/html; charset=utf-8",
	".json": "application/json; charset=utf-8",
	".md": "text/markdown; charset=utf-8",
	".py": "text/x-python; charset=utf-8",
	".svg": "image/svg+xml; charset=utf-8",
	".png": "image/png",
	".js": "application/javascript; charset=utf-8",
	".txt": "text/plain; charset=utf-8",
};

/** 所有资源响应统一携带的三件套（见文件头 ★ 段） */
function corsHeaders(out) {
	out.set("Access-Control-Allow-Origin", "*");
	out.set("Cross-Origin-Resource-Policy", "cross-origin");
	out.set("X-Content-Type-Options", "nosniff");
	return out;
}

/**
 * 目录形态的请求缺尾斜杠 ⇒ 301 补上。
 *
 * 站点页面里全是**相对链接**（'contract/x.md'、'LICENSE'）且没有 '<base>'。
 * 浏览器在无斜杠目录上会把 'contract/x.md' 解析到错误顶层。GitHub Pages
 * 会自动 301 补斜杠；Cloudflare 与 EdgeOne 都不会 —— 这道判断由本 Worker 负责。
 */
function dirRedirect(pathname) {
	if (pathname === "/" || pathname.endsWith("/")) return null;
	const segs = pathname.split("/").filter(Boolean);
	// 非法路径段（.. / . / 空）一律不跳 —— 让后续 404，不要 301 到怪路径
	if (segs.some((x) => x === "" || x === ".." || x === ".")) return null;
	const lastSeg = segs[segs.length - 1] || "";
	if (lastSeg.includes(".")) return null; // 有扩展名 ⇒ 文件
	// 白名单里的顶层无扩展名文件（LICENSE 等）是真实文件，不补斜杠
	if (segs.length === 1 && SITE_BARE_NAMES.has(lastSeg)) return null;
	return pathname + "/";
}

/**
 * release 字节的代理：/<owner>/<repo>/releases/download/<tag>/<file>
 *
 * 与 EO 的差别：EO 用 ModifyOrigin + UpstreamFollowRedirect 在边缘跟随；
 * 本 Worker 的 fetch 默认 redirect: "follow"（hop 上限 20），直接 fetch
 * 上游 URL，字节经 Cloudflare 边缘回给用户。Range / 条件请求头透传，
 * 所以大文件 5MiB 分块 Range 与 206 语义都保持。
 */
async function serveRelease(pathname, request) {
	const segs = pathname.split("/").filter(Boolean);
	if (segs.length !== 6) return null;
	if (segs[2] !== "releases" || segs[3] !== "download") return null;
	if (!segs.every((x) => x !== "." && x !== ".." && x.length > 0 && x.length <= 128)) {
		return null;
	}
	const [owner, repo, tag, file] = [segs[0], segs[1], segs[4], segs[5]];
	const upstream = `https://github.com/${owner}/${repo}/releases/download/${tag}/${file}`;

	const headers = {};
	for (const h of ["range", "if-none-match", "if-modified-since"]) {
		const v = request.headers.get(h);
		if (v) headers[h] = v;
	}
	let res;
	try {
		res = await fetch(upstream, { method: request.method, headers });
	} catch (_) {
		return new Response("Release upstream unreachable", { status: 502 });
	}
	if (res.status === 404) return null;

	const out = corsHeaders(new Headers());
	// cache-control / expires 在透传列表里（2026-11-04 裁定：三条线统一透传）
	for (const h of ["content-type", "content-length", "content-range", "accept-ranges",
	                 "etag", "last-modified", "cache-control", "expires"]) {
		const v = res.headers.get(h);
		if (v) out.set(h, v);
	}
	out.set("Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges, ETag");
	// ★ 强缓存（2026-11-04 裁定）：release 资产不可变（base 含固定 tag，同一
	//   URL 的字节与 ETag 实测稳定）⇒ 1 年 + immutable；上游给的是 no-cache
	//   （Azure Blob），不能透传，必须自己设。与 EO 线语义一致。
	out.set("Cache-Control",
		res.status === 200 || res.status === 206
			? "public, max-age=31536000, immutable"
			: "no-store");
	return new Response(request.method === "HEAD" ? null : res.body, {
		status: res.status,
		headers: out,
	});
}

/** 站点产物运行期回源。返回 null 表示「不该处理」，交给 404。 */
async function serveSite(pathname, request) {
	const to = dirRedirect(pathname);
	if (to) return { redirect: to };

	// 根 "/" → index.html；其余去掉前导斜杠即为产物内相对路径
	const rel = pathname === "/" ? "index.html" : pathname.replace(/^\/+/, "");

	// 只允许普通相对路径 + 白名单。不做「任意路径都回源」——那会变成开放代理
	// （能借本站打 GitHub、也能探别人仓的私有分支路径）。
	if (!rel || rel.split("/").some((s) => s === "" || s === ".." || s === ".")) {
		return null;
	}

	const lastSeg = rel.split("/").pop();
	const hasExt = lastSeg.includes(".");
	let ext = "";
	if (!hasExt) {
		const bare = !rel.includes("/") && SITE_BARE_NAMES.has(rel);
		if (!bare) {
			// 无扩展名且不在白名单：多半是**目录**（缺尾斜杠），补斜杠让
			// 浏览器把相对链接基准修正；若补完仍不存在，再进来就是 404。
			return { redirect: rel.replace(/\/+$/, "") + "/" };
		}
	} else {
		ext = "." + lastSeg.split(".").pop().toLowerCase();
		if (!SITE_ALLOWED_EXT.has(ext)) return null;
	}

	const upstream = `${SITE_UPSTREAM}/${rel}`;
	const headers = {};
	// 条件请求透传：raw 支持 ETag，命中就省一次整包
	const inm = request.headers.get("if-none-match");
	if (inm) headers["If-None-Match"] = inm;

	let res;
	try {
		res = await fetch(upstream, { headers });
	} catch (_) {
		return "upstream-error";
	}
	if (res.status === 404) return null;

	const out = corsHeaders(new Headers());
	out.set("Content-Type", TYPES[ext] || "application/octet-stream");
	out.set("Cache-Control", "public, max-age=300");
	out.set("Access-Control-Expose-Headers", "ETag, Content-Length");
	// 上游的 ETag 直接沿用（它就是内容哈希），下游条件请求因此能一路命中
	const etag = res.headers.get("etag");
	if (etag) out.set("ETag", etag);
	const cl = res.headers.get("content-length");
	if (cl) out.set("Content-Length", cl);

	return new Response(request.method === "HEAD" ? null : res.body, {
		status: res.status,
		headers: out,
	});
}

export default {
	async fetch(request) {
		const url = new URL(request.url);

		if (request.method === "OPTIONS") {
			return new Response(null, {
				status: 204,
				headers: {
					"Access-Control-Allow-Origin": "*",
					"Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
					"Access-Control-Allow-Headers": "*",
					"Access-Control-Max-Age": "86400",
				},
			});
		}

		if (request.method !== "GET" && request.method !== "HEAD") {
			return new Response("Method Not Allowed", {
				status: 405,
				headers: { Allow: "GET, HEAD, OPTIONS", "Content-Type": "text/plain; charset=utf-8" },
			});
		}

		if (url.pathname === "/health") {
			return new Response(
				JSON.stringify({
					ok: true,
					home: "Static-Contract main /worker",
					site: { upstream: SITE_UPSTREAM, mode: "runtime-fetch" },
					release: { mode: "proxy", follow: "fetch-redirect" },
				}),
				{ status: 200, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } },
			);
		}

		// ① release 字节代理先于站点回源判：Release 形状不可能与站点文件
		//    同名（站点文件都在顶层或 contract/ tools/ 下，无 releases/download 段）。
		const relRes = await serveRelease(url.pathname, request);
		if (relRes) return relRes;

		// ② 其余全部按站点产物运行期回源
		const siteRes = await serveSite(url.pathname, request);
		if (siteRes && siteRes.redirect) {
			const target = new URL(request.url);
			target.pathname = siteRes.redirect;
			return new Response(null, {
				status: 301,
				headers: { Location: target.toString(), "Cache-Control": "public, max-age=60" },
			});
		}
		if (siteRes === "upstream-error") {
			return new Response("Static site upstream unreachable", {
				status: 502,
				headers: { "Content-Type": "text/plain; charset=utf-8" },
			});
		}
		if (siteRes) return siteRes;
		return new Response("Not Found", {
			status: 404,
			headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
		});
	},
};
