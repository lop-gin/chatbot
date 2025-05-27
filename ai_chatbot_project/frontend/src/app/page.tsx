'use client';

import { useState, FormEvent } from 'react';

// Define the structure of the backend response
interface ChatResponse {
  sql_query: string | null;
  explanation: string | null;
  data: Record<string, any>[] | null;
  chart_url: string | null;
}

export default function ChatPage() {
  const [inputValue, setInputValue] = useState<string>('');
  const [apiResponse, setApiResponse] = useState<ChatResponse | null>(null); // Updated state type
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setError(null);
    setApiResponse(null); // Clear previous results

    try {
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: inputValue }),
      });

      if (!res.ok) {
        // Try to parse error response from backend
        let errorMsg = `HTTP error! status: ${res.status}`;
        try {
            const errorData = await res.json();
            errorMsg = errorData.detail || errorData.explanation || errorMsg;
        } catch (e) {
            // Ignore if error response is not JSON
        }
        throw new Error(errorMsg);
      }

      const data: ChatResponse = await res.json();
      setApiResponse(data);
    } catch (e: any) {
      console.error('Fetch error:', e);
      setError(e.message || 'Failed to fetch response.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center p-4 md:p-8 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <div className="w-full max-w-4xl space-y-6">
        {/* Input Section */}
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
          <h1 className="text-3xl font-bold text-center text-indigo-600 dark:text-indigo-400 mb-6">
            AI Chatbot for Data Visualization
          </h1>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="queryInput" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Your Query:
              </label>
              <input
                id="queryInput"
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="e.g., What is the distribution of attendees by profession?"
                className="mt-1 block w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-gray-700 dark:text-white transition-shadow duration-150 ease-in-out hover:shadow-md"
                disabled={isLoading}
              />
            </div>
            <button
              type="submit"
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition-opacity duration-150 ease-in-out"
              disabled={isLoading}
            >
              {isLoading ? (
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              ) : 'Send Query'}
            </button>
          </form>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/30 p-4 border border-red-300 dark:border-red-700 text-red-700 dark:text-red-300 rounded-lg shadow">
            <p className="font-semibold text-sm">Error:</p>
            <p className="text-xs">{error}</p>
          </div>
        )}

        {/* Response Sections */}
        {apiResponse && (
          <div className="space-y-6">
            {/* Explanation Section */}
            {apiResponse.explanation && (
              <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
                <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-200 mb-3">Explanation:</h2>
                <p className="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap">{apiResponse.explanation}</p>
              </div>
            )}

            {/* SQL Query Section */}
            {apiResponse.sql_query && (
              <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
                <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-200 mb-3">Generated SQL Query:</h2>
                <pre className="bg-gray-100 dark:bg-gray-700 p-4 rounded-md overflow-x-auto text-sm">
                  <code className="text-gray-800 dark:text-gray-200">{apiResponse.sql_query}</code>
                </pre>
              </div>
            )}

            {/* Data Table Section */}
            {apiResponse.data && apiResponse.data.length > 0 && (
              <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
                <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-200 mb-3">Data Preview:</h2>
                <div className="overflow-x-auto max-h-96"> {/* Scrollable container for table */}
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 border border-gray-200 dark:border-gray-700 text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-700 sticky top-0">
                      <tr>
                        {Object.keys(apiResponse.data[0]).map((key) => (
                          <th key={key} scope="col" className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                            {key.replace(/_/g, ' ')}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {apiResponse.data.map((row, rowIndex) => (
                        <tr key={rowIndex} className={`${rowIndex % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-gray-50 dark:bg-gray-700/50'} hover:bg-gray-100 dark:hover:bg-gray-700`}>
                          {Object.values(row).map((value, cellIndex) => (
                            <td key={cellIndex} className="px-4 py-2 whitespace-nowrap text-xs text-gray-700 dark:text-gray-300">
                              {typeof value === 'boolean' ? value.toString() : value}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            {apiResponse.data === null && apiResponse.sql_query && !error && ( // Show if SQL was generated but no data returned (and no BQ error already handled by explanation)
                 !apiResponse.explanation?.toLowerCase().includes("no data") && // Avoid duplicate messages if explanation already says it
                <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
                    <p className="text-sm text-gray-600 dark:text-gray-300">No data returned for the query.</p>
                </div>
            )}


            {/* Chart Section */}
            {apiResponse.chart_url && (
              <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
                <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-200 mb-3">Chart:</h2>
                <iframe
                  src={`http://localhost:8000${apiResponse.chart_url}`}
                  width="100%"
                  height="500px" // Adjusted height
                  style={{ border: '1px solid #e2e8f0', borderRadius: '0.375rem' }} // Tailwind: border-gray-300, rounded-md
                  title="Generated Chart"
                ></iframe>
              </div>
            )}
            {apiResponse.chart_url === null && apiResponse.sql_query && !error && ( // Show if SQL was generated but no chart (and no BQ error)
                !apiResponse.explanation?.toLowerCase().includes("no chart") && // Avoid duplicate messages
                <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg">
                     <p className="text-sm text-gray-600 dark:text-gray-300">No chart could be generated for this query or data.</p>
                </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
