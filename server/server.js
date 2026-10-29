import 'dotenv/config';
import connectCloudinary from './configs/cloudinary.js';
import app from './app.js';

await connectCloudinary()

const PORT = process.env.PORT || 3000;

app.listen(PORT, ()=>{
    console.log('Server is running on port', PORT);
})
