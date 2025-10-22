import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import axios from 'axios';
import { Search, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';

interface EligibilityResult {
  status: string;
  plan_name: string | null;
  copay: string | null;
  deductible: string | null;
  oop_max: string | null;
  cached: boolean;
  check_date: string;
}

export function EligibilityCheck() {
  const [patientId, setPatientId] = useState('');
  const [providerNPI, setProviderNPI] = useState('1234567890'); // Default NPI

  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const mutation = useMutation({
    mutationFn: async (data: { patient_id: string; provider_npi: string }) => {
      const response = await axios.post<EligibilityResult>(
        `${API_BASE}/api/eligibility/check`,
        data
      );
      return response.data;
    }
  });

  const handleCheck = () => {
    if (!patientId.trim()) {
      alert('Please enter a Patient ID');
      return;
    }
    if (!providerNPI.trim()) {
      alert('Please enter a Provider NPI');
      return;
    }
    mutation.mutate({ patient_id: patientId, provider_npi: providerNPI });
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4">
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Search className="h-6 w-6" />
            Insurance Eligibility Check
          </h2>
          <p className="text-blue-100 text-sm mt-1">
            Real-time verification in under 3 seconds
          </p>
        </div>

        {/* Form */}
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Patient ID
            </label>
            <input
              type="text"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              placeholder="Enter FHIR Patient resource ID"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              disabled={mutation.isPending}
            />
            <p className="mt-1 text-xs text-gray-500">
              Example: patient-123 (use test patient ID from Medplum)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Provider NPI
            </label>
            <input
              type="text"
              value={providerNPI}
              onChange={(e) => setProviderNPI(e.target.value)}
              placeholder="Enter 10-digit NPI"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              disabled={mutation.isPending}
            />
          </div>

          <button
            onClick={handleCheck}
            disabled={mutation.isPending}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 px-6 rounded-lg font-semibold hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center gap-2"
          >
            {mutation.isPending ? (
              <>
                <Clock className="h-5 w-5 animate-spin" />
                Checking...
              </>
            ) : (
              <>
                <Search className="h-5 w-5" />
                Check Eligibility
              </>
            )}
          </button>
        </div>

        {/* Error State */}
        {mutation.isError && (
          <div className="mx-6 mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
            <XCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-red-900 mb-1">Error</h4>
              <p className="text-sm text-red-800">
                {(mutation.error as Error).message || 'Failed to check eligibility'}
              </p>
              <p className="text-xs text-red-700 mt-2">
                Make sure the Patient ID exists in Medplum and has insurance coverage.
              </p>
            </div>
          </div>
        )}

        {/* Success State */}
        {mutation.isSuccess && mutation.data && (
          <div className="mx-6 mb-6 p-6 bg-gradient-to-br from-green-50 to-blue-50 border border-green-200 rounded-lg">
            {/* Status Badge */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-6 w-6 text-green-600" />
                <h3 className="text-lg font-semibold text-gray-900">
                  {mutation.data.status === 'active' ? 'Coverage Active' : 'Coverage Inactive'}
                </h3>
              </div>
              {mutation.data.cached && (
                <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                  Cached result
                </span>
              )}
            </div>

            {/* Results Grid */}
            <dl className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-white p-4 rounded-lg">
                <dt className="text-xs font-medium text-gray-500 uppercase">Status</dt>
                <dd className="mt-1 text-lg font-semibold capitalize text-gray-900">
                  {mutation.data.status}
                </dd>
              </div>

              <div className="bg-white p-4 rounded-lg">
                <dt className="text-xs font-medium text-gray-500 uppercase">Plan</dt>
                <dd className="mt-1 text-lg font-semibold text-gray-900">
                  {mutation.data.plan_name || 'N/A'}
                </dd>
              </div>

              <div className="bg-white p-4 rounded-lg">
                <dt className="text-xs font-medium text-gray-500 uppercase">Copay</dt>
                <dd className="mt-1 text-lg font-semibold text-blue-600">
                  {mutation.data.copay || 'N/A'}
                </dd>
              </div>

              <div className="bg-white p-4 rounded-lg">
                <dt className="text-xs font-medium text-gray-500 uppercase">Deductible</dt>
                <dd className="mt-1 text-lg font-semibold text-blue-600">
                  {mutation.data.deductible || 'N/A'}
                </dd>
              </div>

              <div className="bg-white p-4 rounded-lg col-span-2">
                <dt className="text-xs font-medium text-gray-500 uppercase">Out-of-Pocket Max</dt>
                <dd className="mt-1 text-lg font-semibold text-blue-600">
                  {mutation.data.oop_max || 'N/A'}
                </dd>
              </div>
            </dl>

            {/* AI Insight */}
            <div className="bg-blue-50 p-4 rounded-lg flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="font-semibold text-blue-900 text-sm mb-1">
                  🤖 AI Insight
                </h4>
                <p className="text-sm text-blue-800">
                  {mutation.data.status === 'active'
                    ? 'Coverage is active. No prior authorization required for routine office visits. Patient may have copay due at time of service.'
                    : 'Coverage appears inactive. Verify with patient and contact payer directly. Do not proceed with services without payment arrangement.'}
                </p>
              </div>
            </div>

            {/* Timestamp */}
            <div className="mt-4 text-xs text-gray-500 text-center">
              Checked: {new Date(mutation.data.check_date).toLocaleString()}
            </div>
          </div>
        )}

        {/* Help Text */}
        <div className="bg-gray-50 px-6 py-4 border-t border-gray-200">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">💡 Quick Tips</h4>
          <ul className="text-xs text-gray-600 space-y-1">
            <li>• Results are cached for 24 hours to save API costs</li>
            <li>• Coverage status updates in real-time from payer</li>
            <li>• Use before each appointment to verify eligibility</li>
            <li>• AI automatically checks for authorization requirements</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
