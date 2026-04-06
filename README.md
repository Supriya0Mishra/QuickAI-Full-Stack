# ⚡ QuickAI – Full Stack AI SaaS Platform

> An AI-powered full-stack web application that enables users to generate, manage, and publish AI-generated content using state-of-the-art APIs — built with React, Node.js, and PostgreSQL.

---

## 🎬 Demo

> 📌 *Demo video coming soon — will be added after recording.*

<!-- Once you have a demo, replace the line above with:
[![Watch the demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://youtu.be/YOUR_VIDEO_ID)
-->

---

## 🚀 Features

- 🔐 **Authentication** — Secure sign-up/login with Clerk (OAuth + Email)
- 🤖 **AI Content Generation** — Generate text content powered by Google Gemini API
- 🖼️ **AI Image Generation** — Create images using Clipdrop API
- 📄 **PDF Parsing** — Upload and extract content from PDF documents
- ☁️ **Cloud Image Storage** — Images stored and served via Cloudinary
- 🗄️ **Persistent Storage** — All user creations saved to Neon (PostgreSQL) database
- 📢 **Publish & Like** — Users can publish creations and like others' content
- 📱 **Responsive UI** — Clean, modern interface built with Tailwind CSS v4

---

## 🛠️ Tech Stack

### Frontend
| Technology | Purpose |
|---|---|
| React 19 | UI Framework |
| Vite | Build Tool |
| Tailwind CSS v4 | Styling |
| Clerk (React SDK) | Authentication |
| React Router DOM v7 | Client-side Routing |
| Axios | HTTP Requests |
| Lucide React | Icons |
| React Hot Toast | Notifications |
| React Markdown | Render AI Markdown Output |

### Backend
| Technology | Purpose |
|---|---|
| Node.js + Express.js | Server & REST API |
| Clerk (Express SDK) | Auth Middleware |
| Neon (PostgreSQL) | Serverless Database |
| Cloudinary | Image Storage & CDN |
| Google Gemini API | AI Text Generation |
| Clipdrop API | AI Image Generation |
| OpenAI SDK | AI Utilities |
| Multer | File Upload Handling |
| pdf-parse | PDF Text Extraction |

---

## 📁 Project Structure

```
QuickAI-Full-Stack/
├── client/                 # React frontend (Vite)
│   ├── src/
│   ├── public/
│   ├── index.html
│   └── package.json
├── server/                 # Express.js backend
│   ├── controllers/
│   ├── routes/
│   ├── middlewares/
│   ├── configs/
│   ├── server.js
│   └── package.json
└── README.md
```

---

## ⚙️ Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/en/download/) installed
- Accounts set up for:
  - [Neon](https://neon.com) — PostgreSQL database
  - [Cloudinary](https://cloudinary.com/users/register_free) — Image hosting
  - [Clerk](https://clerk.com) — Authentication
  - [Clipdrop](https://clipdrop.co/apis) — AI image generation
  - [Google AI Studio](https://aistudio.google.com/apikey) — Gemini API key

---

### 🗄️ Database Setup

Run the following SQL in your Neon SQL Editor:

```sql
CREATE TABLE creations (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  prompt TEXT NOT NULL,
  content TEXT NOT NULL,
  type TEXT NOT NULL,
  publish BOOLEAN DEFAULT FALSE,
  likes TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### 🖥️ Running the Server

```bash
# Navigate to server folder
cd server

# Install dependencies
npm install

# Add your environment variables to .env
# (See Environment Variables section below)

# Start the server
npm run server
```

Server runs at: `http://localhost:3000`

---

### 💻 Running the Client

> ⚠️ Make sure the server is running before starting the client.

```bash
# Navigate to client folder
cd client

# Install dependencies
npm install

# Add your environment variables to .env
# (See Environment Variables section below)

# Start the dev server
npm run dev
```

Client runs at: `http://localhost:5173`

---

## 🔑 Environment Variables

### Server — `server/.env`

```env
PORT=3000
DATABASE_URL=your_neon_database_url
CLOUDINARY_NAME=your_cloudinary_name
CLOUDINARY_API_KEY=your_cloudinary_api_key
CLOUDINARY_API_SECRET=your_cloudinary_api_secret
CLERK_SECRET_KEY=your_clerk_secret_key
CLIPDROP_API=your_clipdrop_api_key
GEMINI_API_KEY=your_gemini_api_key
```

### Client — `client/.env`

```env
VITE_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
VITE_BASE_URL=http://localhost:3000
```

---

## 📸 Screenshots

> 📌 *Screenshots will be added soon.*

---

## 👩‍💻 Author

**Supriya Mishra**
- GitHub: [@supriya](https://github.com/your-github-username)
- LinkedIn: [Supriya Mishra](https://linkedin.com/in/your-linkedin)

---

## 📄 License

This project is for educational and portfolio purposes.
