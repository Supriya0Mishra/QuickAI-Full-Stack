import { describe, it, expect, vi, beforeEach } from 'vitest';
import request from 'supertest';

// Fakes for every external service, so tests need no keys or network.
const mocks = vi.hoisted(() => ({
    state: { plan: 'free', freeUsage: 0 },
    sql: null,
    aiCreate: null,
    updateUserMetadata: null,
}));

vi.mock('@clerk/express', () => {
    mocks.updateUserMetadata = vi.fn(async () => {});
    return {
        clerkMiddleware: () => (req, res, next) => {
            req.auth = () => ({ userId: 'user_1', has: async () => mocks.state.plan === 'premium' });
            next();
        },
        requireAuth: () => (req, res, next) => next(),
        clerkClient: {
            users: {
                getUser: async () => ({ privateMetadata: { free_usage: mocks.state.freeUsage } }),
                updateUserMetadata: (...args) => mocks.updateUserMetadata(...args),
            },
        },
    };
});

vi.mock('../configs/db.js', () => {
    mocks.sql = vi.fn(async () => []);
    return { default: (...args) => mocks.sql(...args) };
});

vi.mock('openai', () => {
    mocks.aiCreate = vi.fn(async () => ({ choices: [{ message: { content: 'AI text' } }] }));
    return {
        default: class {
            chat = { completions: { create: (...args) => mocks.aiCreate(...args) } };
        },
    };
});

vi.mock('cloudinary', () => ({
    v2: {
        config: () => {},
        uploader: { upload: async () => ({ secure_url: 'https://img/1.png', public_id: 'p1' }) },
        url: () => 'https://img/1.png',
    },
}));

vi.mock('pdf-parse/lib/pdf-parse.js', () => ({ default: async () => ({ text: 'resume text' }) }));

const { default: app } = await import('../app.js');

const PNG = Buffer.from('89504e470d0a1a0a', 'hex');

beforeEach(() => {
    mocks.state.plan = 'free';
    mocks.state.freeUsage = 0;
    mocks.sql.mockClear();
    mocks.aiCreate.mockClear();
    mocks.updateUserMetadata.mockClear();
});

describe('POST /api/ai/generate-article', () => {
    it('rejects a length that is not one of the allowed values', async () => {
        const res = await request(app).post('/api/ai/generate-article').send({ prompt: 'AI in schools', length: 100000 });

        expect(res.status).toBe(400);
        expect(res.body.success).toBe(false);
        expect(mocks.aiCreate).not.toHaveBeenCalled();
    });

    it('rejects an empty prompt', async () => {
        const res = await request(app).post('/api/ai/generate-article').send({ prompt: '   ', length: 800 });

        expect(res.status).toBe(400);
        expect(res.body.message).toBe('Prompt is required.');
    });

    it('generates an article, saves it and counts free usage', async () => {
        mocks.state.freeUsage = 3;
        const res = await request(app).post('/api/ai/generate-article').send({ prompt: 'AI in schools', length: 1200 });

        expect(res.status).toBe(200);
        expect(res.body).toEqual({ success: true, content: 'AI text' });
        expect(mocks.aiCreate).toHaveBeenCalledWith(expect.objectContaining({ max_tokens: 1200 }));
        expect(mocks.sql).toHaveBeenCalledTimes(1);
        expect(mocks.updateUserMetadata).toHaveBeenCalledWith('user_1', { privateMetadata: { free_usage: 4 } });
    });

    it('returns 403 when the free limit is reached', async () => {
        mocks.state.freeUsage = 10;
        const res = await request(app).post('/api/ai/generate-article').send({ prompt: 'AI in schools', length: 800 });

        expect(res.status).toBe(403);
        expect(mocks.aiCreate).not.toHaveBeenCalled();
    });

    it('hides internal error details behind a 500', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});
        mocks.aiCreate.mockRejectedValueOnce(new Error('Gemini key abc123 is invalid'));

        const res = await request(app).post('/api/ai/generate-article').send({ prompt: 'AI in schools', length: 800 });

        expect(res.status).toBe(500);
        expect(res.body.message).not.toContain('abc123');
    });
});

describe('premium-only endpoints', () => {
    it('returns 403 for free users on generate-image', async () => {
        const res = await request(app).post('/api/ai/generate-image').send({ prompt: 'a red fox' });

        expect(res.status).toBe(403);
    });

    it('rejects an object name that is not one plain word', async () => {
        mocks.state.plan = 'premium';
        const res = await request(app)
            .post('/api/ai/remove-image-object')
            .field('object', 'cat,e_grayscale')
            .attach('image', PNG, { filename: 'a.png', contentType: 'image/png' });

        expect(res.status).toBe(400);
        expect(mocks.sql).not.toHaveBeenCalled();
    });

    it('asks for an image when none is uploaded', async () => {
        mocks.state.plan = 'premium';
        const res = await request(app).post('/api/ai/remove-image-background').send({});

        expect(res.status).toBe(400);
        expect(res.body.message).toBe('Please upload an image.');
    });

    it('rejects a resume that is not a PDF', async () => {
        mocks.state.plan = 'premium';
        const res = await request(app)
            .post('/api/ai/resume-review')
            .attach('resume', PNG, { filename: 'resume.png', contentType: 'image/png' });

        expect(res.status).toBe(400);
        expect(res.body.message).toBe('Only PDF files are allowed.');
    });
});

describe('POST /api/user/toggle-like-creation', () => {
    it('returns 404 when the creation does not exist', async () => {
        const res = await request(app).post('/api/user/toggle-like-creation').send({ id: 999 });

        expect(res.status).toBe(404);
    });

    it('rejects an invalid id', async () => {
        const res = await request(app).post('/api/user/toggle-like-creation').send({ id: 'abc' });

        expect(res.status).toBe(400);
    });
});
