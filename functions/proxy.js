// functions/proxy.js
export async function onRequest({ request }) {
  // 代理目标 URL（GitHub 上的 raw 文件链接）
  const targetUrl = 'https://raw.githubusercontent.com/yd072/iptv-api/refs/heads/master/output/result.txt';

  // 请求目标 URL
  const response = await fetch(targetUrl);
  
  // 返回 GitHub 文件的内容
  return new Response(await response.text(), {
    status: response.status,
    headers: {
      'Content-Type': 'text/plain',
      ...response.headers
    }
  });
}
