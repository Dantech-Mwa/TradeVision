// api/gemini.js — SERVER-SIDE ONLY (Never exposed to users)
const GEMINI_KEY = 'AIzaSyA7L2Fv1TUNwMPDwdwW1JqjaCMNiEXb0To'; // Your key — safe here

export default async function handler(req, res) {
  // Only allow POST
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { prompt } = req.body;
  if (!prompt) {
    return res.status(400).json({ error: 'Missing prompt' });
  }

  try {
    const response = await fetch(
      'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-002:generateContent',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-goog-api-key': GEMINI_KEY
        },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            temperature: 0.7,
            maxOutputTokens: 400
          }
        })
      }
    );

    if (!response.ok) {
      const err = await response.text();
      throw new Error(`Gemini API error: ${response.status} - ${err}`);
    }

    const data = await response.json();
    const insight = data.candidates?.[0]?.content?.parts?.[0]?.text || 'No response from AI';

    res.status(200).json({ insight });
  } catch (error) {
    console.error('Gemini Proxy Error:', error);
    res.status(500).json({ error: 'AI analysis failed' });
  }
}
