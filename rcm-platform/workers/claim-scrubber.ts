/**
 * Cloudflare Workers AI - Claim Scrubber
 * Checks medical claims for errors before submission
 */

export interface Env {
  AI: any;
}

interface ClaimData {
  patient: {
    name: string;
    dob: string;
  };
  cpt_codes: string[];
  icd10_codes: string[];
  payer: string;
  provider_npi: string;
  place_of_service?: string;
}

interface ScrubResult {
  ready: boolean;
  errors: string[];
  warnings: string[];
  confidence: number;
  suggestions?: string[];
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle OPTIONS for CORS
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    if (request.method !== 'POST') {
      return new Response('Method not allowed', {
        status: 405,
        headers: corsHeaders
      });
    }

    try {
      const claim: ClaimData = await request.json();

      // Validate input
      if (!claim.cpt_codes || !claim.icd10_codes) {
        return new Response(JSON.stringify({
          ready: false,
          errors: ['Missing CPT codes or ICD-10 codes'],
          warnings: [],
          confidence: 0
        }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      // Call Cloudflare AI
      const ai = new Ai(env.AI);

      const prompt = `You are a medical billing expert AI. Review this claim for submission errors.

CLAIM DETAILS:
- Patient: ${claim.patient.name} (DOB: ${claim.patient.dob})
- CPT Codes: ${claim.cpt_codes.join(', ')}
- ICD-10 Codes: ${claim.icd10_codes.join(', ')}
- Payer: ${claim.payer}
- Provider NPI: ${claim.provider_npi}
${claim.place_of_service ? `- Place of Service: ${claim.place_of_service}` : ''}

Check for these common errors:
1. CPT-ICD-10 medical necessity mismatch
2. Missing or incorrect modifiers
3. Incorrect place of service code
4. Prior authorization required but not documented
5. Bundling issues (codes that can't be billed together)
6. Age/gender inappropriate codes
7. Units > 1 without appropriate documentation

Return ONLY a valid JSON object in this exact format:
{
  "ready": true or false,
  "errors": ["error message 1", "error message 2"],
  "warnings": ["warning 1"],
  "confidence": 0.85,
  "suggestions": ["suggestion 1"]
}

Be specific about errors. If no errors found, set ready=true and errors=[].`;

      const response = await ai.run('@cf/meta/llama-3.2-11b-vision-instruct', {
        prompt,
        max_tokens: 500
      });

      // Parse AI response
      let result: ScrubResult;

      try {
        const text = (response as any).response || '';

        // Try to extract JSON from response
        const jsonMatch = text.match(/\{[\s\S]*\}/);

        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0]);

          result = {
            ready: parsed.ready ?? true,
            errors: parsed.errors || [],
            warnings: parsed.warnings || [],
            confidence: parsed.confidence ?? 0.85,
            suggestions: parsed.suggestions || []
          };
        } else {
          // Fallback if AI doesn't return proper JSON
          result = {
            ready: true,
            errors: [],
            warnings: ['AI response parsing failed - manual review recommended'],
            confidence: 0.5,
            suggestions: []
          };
        }
      } catch (parseError) {
        // Error parsing AI response
        result = {
          ready: false,
          errors: ['AI scrubber error - manual review required'],
          warnings: [],
          confidence: 0.0,
          suggestions: []
        };
      }

      // Add metadata
      const enrichedResult = {
        ...result,
        timestamp: new Date().toISOString(),
        model: '@cf/meta/llama-3.2-11b-vision-instruct',
        claim_summary: {
          cpt_count: claim.cpt_codes.length,
          icd10_count: claim.icd10_codes.length
        }
      };

      return new Response(JSON.stringify(enrichedResult), {
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json'
        }
      });

    } catch (error) {
      console.error('Claim scrubber error:', error);

      return new Response(JSON.stringify({
        ready: false,
        errors: ['Internal scrubber error'],
        warnings: [],
        confidence: 0.0
      }), {
        status: 500,
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json'
        }
      });
    }
  }
};
