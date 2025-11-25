import React, { useState } from 'react';
import { Github, ArrowRight } from 'lucide-react';

const Home = () => {
    const [owner, setOwner] = useState('');
    const [repo, setRepo] = useState('');
    const [loading, setLoading] = useState(false);

    const handleAnalyze = (e) => {
        e.preventDefault();
        if (!owner || !repo) return;

        setLoading(true);
        // Redirect to backend auth start endpoint
        // Using window.location.href to navigate to the backend URL
        const backendUrl = 'http://localhost:8000/api/auth/start';
        window.location.href = `${backendUrl}?owner=${owner}&repo=${repo}`;
    };

    return (
        <div className="container">
            <div className="glass-panel form-group">
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
                    <Github size={48} color="#fff" />
                </div>
                <h1>License Checker</h1>
                <p>Analyze GitHub repositories for license compatibility.</p>

                <form onSubmit={handleAnalyze} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
                    <input
                        type="text"
                        placeholder="GitHub Owner (e.g. facebook)"
                        value={owner}
                        onChange={(e) => setOwner(e.target.value)}
                        className="glass-input"
                        required
                    />
                    <input
                        type="text"
                        placeholder="Repository Name (e.g. react)"
                        value={repo}
                        onChange={(e) => setRepo(e.target.value)}
                        className="glass-input"
                        required
                    />

                    <button type="submit" className="glass-button" disabled={loading}>
                        {loading ? 'Redirecting...' : (
                            <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                                Clone Repository <ArrowRight size={16} />
                            </span>
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default Home;
