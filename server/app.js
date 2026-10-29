import express from 'express';
import cors from 'cors';
import { clerkMiddleware, requireAuth } from '@clerk/express'
import aiRouter from './routes/aiRoutes.js';
import userRouter from './routes/userRoutes.js';
import { errorHandler } from './middlewares/errorHandler.js';

// The app is built here and started in server.js, so tests can import it
// without opening a port.
const app = express()

app.use(cors())
app.use(express.json())
app.use(clerkMiddleware())

app.get('/', (req, res)=>res.send('Server is Live!'))

app.use(requireAuth())

app.use('/api/ai', aiRouter)
app.use('/api/user', userRouter)

app.use(errorHandler)

export default app;
