// api/gemini.js
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const GEMINI_KEY = process.env.GEMINI_API_KEY; // ← Hidden in Vercel
  if (!GEMINI_KEY) {
    return res.status(500).json({ error: 'API key not configured' });
  }

  const { prompt } = req.body;
  if (!prompt) {
    return res.status(400).json({ error: 'Missing prompt' });
  }

  try {
    const response = await fetch(
      'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-goog-api-key': GEMINI_KEY
        },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.7, maxOutputTokens: 400 }
        })
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error?.message || 'Gemini API error');
    }

    const insight = data.candidates?.[0]?.content?.parts?.[0]?.text || 'No response';

    res.status(200).json({ insight });
  } catch (error) {
    console.error('Gemini error:', error);
    res.status(500).json({ error: error.message });
  }
}
