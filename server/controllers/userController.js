import sql from "../configs/db.js";
import { HttpError } from "../utils/httpError.js";


export const getUserCreations = async (req, res)=>{
    const {userId} = req.auth()

    const creations = await sql`SELECT * FROM creations WHERE user_id = ${userId} ORDER BY created_at DESC`;

    res.json({ success: true, creations });
}

export const getPublishedCreations = async (req, res)=>{
    const creations = await sql`
    SELECT * FROM creations WHERE publish = true ORDER BY created_at DESC`;

    res.json({ success: true, creations });
}

export const toggleLikeCreation = async (req, res)=>{
    const {userId} = req.auth()
    const {id} = req.body

    const [creation] = await sql`SELECT * FROM creations WHERE id = ${id}`

    if(!creation){
        throw new HttpError(404, "Creation not found");
    }

    const currentLikes = creation.likes;
    const userIdStr = userId.toString();
    let updatedLikes;
    let message;

    if(currentLikes.includes(userIdStr)){
        updatedLikes = currentLikes.filter((user)=>user !== userIdStr);
        message = 'Creation Unliked'
    }else{
        updatedLikes = [...currentLikes, userIdStr]
        message = 'Creation Liked'
    }

    const formattedArray = `{${updatedLikes.join(',')}}`

    await sql`UPDATE creations SET likes = ${formattedArray}::text[] WHERE id = ${id}`;

    res.json({ success: true, message });
}
