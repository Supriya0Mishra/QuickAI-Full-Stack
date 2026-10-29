import multer from "multer";
import { HttpError } from "../utils/httpError.js";

const storage = multer.diskStorage({});

const onlyTypes = (types, label) => (req, file, cb) => {
    if (types.includes(file.mimetype)) return cb(null, true);
    cb(new HttpError(400, `Only ${label} files are allowed.`));
};

export const imageUpload = multer({
    storage,
    limits: { fileSize: 10 * 1024 * 1024 },
    fileFilter: onlyTypes(['image/png', 'image/jpeg', 'image/webp'], 'PNG, JPEG or WebP'),
});

export const pdfUpload = multer({
    storage,
    limits: { fileSize: 5 * 1024 * 1024 },
    fileFilter: onlyTypes(['application/pdf'], 'PDF'),
});
