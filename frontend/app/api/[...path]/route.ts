import { backend, boundedJson, DemoServiceError, rejectForeignOrigin, serviceError } from '../../../lib/demo-backend';

export const dynamic = 'force-dynamic';
type Context = { params: Promise<{ path: string[] }> };
const publicGet = new Set(['health', 'ready', 'langs', 'content', 'v1/learning/catalog']);
const publicPost = new Set(['analyze', 'quiz', 'sim', 'v1/risk/evaluate']);
const privateGet = new Set(['v1/learning/progress']);
const privatePost = new Set(['v1/learning/completions', 'v1/learning/rewards/30/claim']);
async function proxy(request: Request, context: Context) {
  try {
    const path = (await context.params).path.join('/');
    const post = request.method === 'POST';
    const isPublic = (post ? publicPost : publicGet).has(path);
    const isPrivate = (post ? privatePost : privateGet).has(path);
    if (!isPublic && !isPrivate) throw new DemoServiceError(404, 'Этот API не доступен через интерфейс.');
    if (post) rejectForeignOrigin(request);
    const payload = await backend(`/api/${path}`, request.method, post ? await boundedJson(request) : undefined, isPrivate);
    return Response.json(payload, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) { return serviceError(error); }
}
export const GET = proxy;
export const POST = proxy;
