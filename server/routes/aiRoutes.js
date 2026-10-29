import express from "express";
import { auth } from "../middlewares/auth.js";
import { validate, requireFile } from "../middlewares/validate.js";
import { generateArticle, generateBlogTitle, generateImage, removeImageBackground, removeImageObject, resumeReview } from "../controllers/aiController.js";
import { imageUpload, pdfUpload } from "../configs/multer.js";
import { articleSchema, blogTitleSchema, imageSchema, removeObjectSchema } from "../validators/schemas.js";

const aiRouter = express.Router();

aiRouter.post('/generate-article', validate(articleSchema), auth, generateArticle)
aiRouter.post('/generate-blog-title', validate(blogTitleSchema), auth, generateBlogTitle)
aiRouter.post('/generate-image', validate(imageSchema), auth, generateImage)

aiRouter.post('/remove-image-background', imageUpload.single('image'), requireFile('an image'), auth, removeImageBackground)

aiRouter.post('/remove-image-object', imageUpload.single('image'), requireFile('an image'), validate(removeObjectSchema), auth, removeImageObject)

aiRouter.post('/resume-review', pdfUpload.single('resume'), requireFile('a PDF resume'), auth, resumeReview)

export default aiRouter
