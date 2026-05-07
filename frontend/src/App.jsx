import React, { useState } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';

const API_URL = 'http://localhost:8000/api';

function App() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError('');
    setResponse(null);

    try {
      const res = await axios.post(`${API_URL}/ask`, { question });
      setResponse(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>SQL Agent</h1>
      <p>Ask questions about your database in plain English.</p>
      
      <form onSubmit={handleSubmit} style={{ marginBottom: '20px' }}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What would you like to know?"
          style={{ width: '80%', padding: '10px', fontSize: '16px' }}
          disabled={loading}
        />
        <button 
          type="submit" 
          disabled={loading}
          style={{ padding: '10px 20px', fontSize: '16px', marginLeft: '10px' }}
        >
          {loading ? 'Thinking...' : 'Ask'}
        </button>
      </form>

      {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}

      {response && (
        <div>
          <div style={{ background: '#f5f5f5', padding: '15px', borderRadius: '5px', marginBottom: '20px' }}>
            <h3>Answer</h3>
            <ReactMarkdown>{response.answer}</ReactMarkdown>
          </div>

          <div style={{ background: '#f5f5f5', padding: '15px', borderRadius: '5px', marginBottom: '20px' }}>
            <h3>SQL Query</h3>
            <pre style={{ background: '#333', color: '#fff', padding: '10px', borderRadius: '3px', overflow: 'auto' }}>
              <code>{response.sql}</code>
            </pre>
          </div>

          {response.data && response.data.length > 0 && (
            <div style={{ overflow: 'auto' }}>
              <h3>Results ({response.data.length} rows)</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {response.columns.map((col, idx) => (
                      <th key={idx} style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left', background: '#eee' }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {response.data.map((row, rowIdx) => (
                    <tr key={rowIdx}>
                      {response.columns.map((col, colIdx) => (
                        <td key={colIdx} style={{ border: '1px solid #ddd', padding: '8px' }}>
                          {row[col]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {response.review && (
            <div style={{ background: '#fff3cd', padding: '15px', borderRadius: '5px', marginTop: '20px' }}>
              <h3>Review Info</h3>
              <p>{response.review.text}</p>
              {response.review.corrected_query && (
                <>
                  <h4>Corrected Query</h4>
                  <pre style={{ background: '#333', color: '#fff', padding: '10px', borderRadius: '3px' }}>
                    <code>{response.review.corrected_query}</code>
                  </pre>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
