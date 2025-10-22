import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EligibilityCheck } from './components/EligibilityCheck';
import { Heart } from 'lucide-react';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Heart className="h-8 w-8 text-blue-600" />
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">
                    RCM Platform
                  </h1>
                  <p className="text-sm text-gray-600">
                    AI-Powered Medical Billing
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-3 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">
                  ✓ HIPAA Compliant
                </span>
                <span className="px-3 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                  🤖 AI-Powered
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
          {/* Hero Section */}
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Cut Denials in Half with AI
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Real-time eligibility verification, AI claim scrubbing, and automated denial management.
              Save $4,500+ per month per practice.
            </p>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
              <div className="text-3xl font-bold text-blue-600 mb-2">50%</div>
              <div className="text-sm text-gray-600">Denial Rate Reduction</div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
              <div className="text-3xl font-bold text-green-600 mb-2">&lt;3s</div>
              <div className="text-sm text-gray-600">Eligibility Check Time</div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
              <div className="text-3xl font-bold text-purple-600 mb-2">22X</div>
              <div className="text-sm text-gray-600">Return on Investment</div>
            </div>
          </div>

          {/* Eligibility Check Component */}
          <EligibilityCheck />

          {/* Features */}
          <div className="mt-12 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-semibold mb-3">🤖 AI Claim Scrubber</h3>
              <p className="text-gray-600 text-sm">
                Catches errors before submission. Reduces denials from 15% to 7%.
                Saves $20K/year per practice.
              </p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-semibold mb-3">📝 Auto Appeal Writer</h3>
              <p className="text-gray-600 text-sm">
                Generates professional appeals in seconds. Increases win rate from 60% to 85%.
                Saves $15K/year per practice.
              </p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-semibold mb-3">⚡ Prior Auth Automation</h3>
              <p className="text-gray-600 text-sm">
                Auto-fills forms from clinical notes. Reduces 2 hours to 10 minutes.
                Saves $30K/year per practice.
              </p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-semibold mb-3">🎤 Voice Charge Capture</h3>
              <p className="text-gray-600 text-sm">
                Doctor speaks charges, AI converts to CPT codes. 5 minutes → 30 seconds.
                Physicians love it.
              </p>
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="mt-16 bg-gray-50 border-t border-gray-200">
          <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
            <p className="text-center text-sm text-gray-600">
              © 2025 RCM Platform. HIPAA Compliant. SOC 2 Type II (pending).
            </p>
          </div>
        </footer>
      </div>
    </QueryClientProvider>
  );
}

export default App;
