import OpenAI from "openai";
import sql from "../configs/db.js";
import { clerkClient } from "@clerk/express";
import axios from "axios";
import { v2 as cloudinary } from "cloudinary";
import fs from 'fs'
import pdf from 'pdf-parse/lib/pdf-parse.js'
import { HttpError } from "../utils/httpError.js";

const AI = new OpenAI({
    apiKey: process.env.GEMINI_API_KEY,
    baseURL: "https://generativelanguage.googleapis.com/v1beta/openai/"
});

const FREE_LIMIT = 10;

const requireFreeQuota = (req) => {
    if(req.plan !== 'premium' && req.free_usage >= FREE_LIMIT){
        throw new HttpError(403, "Free limit reached. Upgrade to continue.");
    }
}

const requirePremium = (req) => {
    if(req.plan !== 'premium'){
        throw new HttpError(403, "This feature is only available for premium subscriptions");
    }
}

const countFreeUsage = async (req, userId) => {
    if(req.plan !== 'premium'){
        await clerkClient.users.updateUserMetadata(userId, {
            privateMetadata:{
                free_usage: req.free_usage + 1
            }
        })
    }
}

// Request bodies below are already checked by the zod schemas in validators/schemas.js.

export const generateArticle = async (req, res)=>{
    const { userId } = req.auth();
    const { prompt, length } = req.body;
    requireFreeQuota(req);

    const response = await AI.chat.completions.create({
        model: "gemini-2.0-flash",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.7,
        max_tokens: length,
    });

    const content = response.choices[0].message.content

    await sql` INSERT INTO creations (user_id, prompt, content, type)
    VALUES (${userId}, ${prompt}, ${content}, 'article')`;

    await countFreeUsage(req, userId);

    res.json({ success: true, content})
}

export const generateBlogTitle = async (req, res)=>{
    const { userId } = req.auth();
    const { prompt } = req.body;
    requireFreeQuota(req);

    const response = await AI.chat.completions.create({
        model: "gemini-2.0-flash",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.7,
        max_tokens: 100,
    });

    const content = response.choices[0].message.content

    await sql` INSERT INTO creations (user_id, prompt, content, type)
    VALUES (${userId}, ${prompt}, ${content}, 'blog-title')`;

    await countFreeUsage(req, userId);

    res.json({ success: true, content})
}


export const generateImage = async (req, res)=>{
    const { userId } = req.auth();
    const { prompt, publish } = req.body;
    requirePremium(req);

    const formData = new FormData()
    formData.append('prompt', prompt)
    const {data} = await axios.post("https://clipdrop-api.co/text-to-image/v1", formData, {
        headers: {'x-api-key': process.env.CLIPDROP_API_KEY,},
        responseType: "arraybuffer",
    })

    const base64Image = `data:image/png;base64,${Buffer.from(data, 'binary').toString('base64')}`;

    const {secure_url} = await cloudinary.uploader.upload(base64Image)

    await sql` INSERT INTO creations (user_id, prompt, content, type, publish)
    VALUES (${userId}, ${prompt}, ${secure_url}, 'image', ${publish})`;

    res.json({ success: true, content: secure_url})
}

export const removeImageBackground = async (req, res)=>{
    const { userId } = req.auth();
    const image = req.file;
    requirePremium(req);

    const {secure_url} = await cloudinary.uploader.upload(image.path, {
        transformation: [
            {
                effect: 'background_removal',
                background_removal: 'remove_the_background'
            }
        ]
    })

    await sql` INSERT INTO creations (user_id, prompt, content, type)
    VALUES (${userId}, 'Remove background from image', ${secure_url}, 'image')`;

    res.json({ success: true, content: secure_url})
}

export const removeImageObject = async (req, res)=>{
    const { userId } = req.auth();
    const { object } = req.body;
    const image = req.file;
    requirePremium(req);

    const {public_id} = await cloudinary.uploader.upload(image.path)

    const imageUrl = cloudinary.url(public_id, {
        transformation: [{effect: `gen_remove:${object}`}],
        resource_type: 'image'
    })

    await sql` INSERT INTO creations (user_id, prompt, content, type)
    VALUES (${userId}, ${`Removed ${object} from image`}, ${imageUrl}, 'image')`;

    res.json({ success: true, content: imageUrl})
}

export const resumeReview = async (req, res)=>{
    const { userId } = req.auth();
    const resume = req.file;
    requirePremium(req);

    // File type and the 5MB size limit are enforced by pdfUpload in configs/multer.js.
    const dataBuffer = fs.readFileSync(resume.path)
    const pdfData = await pdf(dataBuffer)

    const prompt = `Review the following resume and provide constructive feedback on its strengths, weaknesses, and areas for improvement. Resume Content:\n\n${pdfData.text}`

    const response = await AI.chat.completions.create({
        model: "gemini-2.0-flash",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.7,
        max_tokens: 1000,
    });

    const content = response.choices[0].message.content

    await sql` INSERT INTO creations (user_id, prompt, content, type)
    VALUES (${userId}, 'Review the uploaded resume', ${content}, 'resume-review')`;

    res.json({ success: true, content})
}
