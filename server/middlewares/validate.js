import { HttpError } from "../utils/httpError.js";

// Checks req.body against a zod schema and replaces it with the parsed value.
export const validate = (schema) => (req, res, next) => {
    const result = schema.safeParse(req.body ?? {});
    if (!result.success) {
        return next(new HttpError(400, result.error.issues[0].message));
    }
    req.body = result.data;
    next();
};

export const requireFile = (label) => (req, res, next) => {
    if (!req.file) {
        return next(new HttpError(400, `Please upload ${label}.`));
    }
    next();
};
