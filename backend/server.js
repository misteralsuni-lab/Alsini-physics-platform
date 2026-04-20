const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const { GoogleGenerativeAI } = require('@google/generative-ai');

// Load environment variables from .env
dotenv.config();

const app = express();
const port = process.env.PORT || 5000;

// Security and request parsing middleware
app.use(cors({ 
  origin: '*'
}));
app.use(express.json());

// Initialize Google Generative AI
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

// Define the core persona for the AI Tutor
const SYSTEM_INSTRUCTION = `You are an expert, encouraging Edexcel IGCSE and A-Level Physics Tutor. 
You guide students to the answer using Socratic questioning. 
You never just give them the final answer immediately. 
Format your mathematical explanations cleanly.`;

// Configure the Gemini 2.5 Flash model for speed/cost efficiency & pass the system instruction
const model = genAI.getGenerativeModel({
  model: 'gemini-2.5-flash',
  systemInstruction: SYSTEM_INSTRUCTION,
});

/**
 * POST /api/chat
 * Accepts an array of message history from the frontend and the new message 
 * to generate the next response via Gemini.
 */
app.post('/api/chat', async (req, res) => {
  try {
    console.log('Received payload:', req.body);
    const { history, message } = req.body;

    if (!message) {
      return res.status(400).json({ error: 'A message string is required.' });
    }

    // Initialize the chat session with previous history context
    // Expected history format: [{ role: "user" | "model", parts: [{ text: "..." }] }]
    const chat = model.startChat({
        history: history || [],
    });

    // Send the user's new message
    const result = await chat.sendMessage(message);
    const response = await result.response;
    const text = response.text();

    res.json({ response: text });
  } catch (error) {
    console.error('RAW ERROR OBJECT:', error);
    res.status(500).json({ error: 'Failed to communicate with AI Tutor.' });
  }
});

// Basic ping route to check server health
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'OK', message: 'Backend is running' });
});

// Start the server
app.listen(port, () => {
    console.log(`Backend server running beautifully on port ${port}`);
    console.log(`CORS allows ALL origins (*) temporarily`);
});
