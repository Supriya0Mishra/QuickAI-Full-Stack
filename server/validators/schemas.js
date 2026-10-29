import { z } from "zod";

const prompt = (max) => z.string({ required_error: 'Prompt is required.', invalid_type_error: 'Prompt must be text.' })
    .trim()
    .min(1, 'Prompt is required.')
    .max(max, `Prompt must be at most ${max} characters.`);

// The client offers 800, 1200 and 1600. This value goes into max_tokens,
// so it must never be taken from the request unchecked.
export const ARTICLE_LENGTHS = [800, 1200, 1600];

export const articleSchema = z.object({
    prompt: prompt(2000),
    length: z.number({ required_error: 'Length is required.', invalid_type_error: 'Length must be a number.' }).refine(
        (n) => ARTICLE_LENGTHS.includes(n),
        `Length must be one of ${ARTICLE_LENGTHS.join(', ')}.`
    ),
});

export const blogTitleSchema = z.object({
    prompt: prompt(500),
});

export const imageSchema = z.object({
    prompt: prompt(1000),
    publish: z.boolean().optional().default(false),
});

// The object name is inserted into a Cloudinary transformation string,
// so only allow one plain word.
export const removeObjectSchema = z.object({
    object: z.string({ required_error: 'Object name is required.', invalid_type_error: 'Object name must be text.' })
        .trim()
        .regex(/^[a-zA-Z]{1,30}$/, 'Describe the object in one word, using letters only.'),
});

export const toggleLikeSchema = z.object({
    id: z.coerce.number().int().positive('Invalid creation id.'),
});
