/**
 * Shared GoogleGenAI Client instance configured for server-side execution.
 */
import { GoogleGenAI } from '@google/genai';

export const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-3.8-flash';

let client: GoogleGenAI | undefined;

// Reading saved ideas and artifacts does not require a model API key.
export function getGeminiClient(): GoogleGenAI {
  if (client) return client;
  const apiKey = process.env.GEMINI_API_KEY?.trim();
  if (!apiKey) {
    throw new Error('GEMINI_API_KEY is required to generate new idea enrichment.');
  }
  client = new GoogleGenAI({
    apiKey,
    httpOptions: {
      headers: {
        'User-Agent': 'aistudio-build',
      },
    },
  });
  return client;
}
