import React, { useState, useEffect } from 'react';

const PricingManager = () => {
    const [pricingData, setPricingData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [message, setMessage] = useState('');

    // 1. Fetch current prices from the Backend
    const fetchPrices = async () => {
        try {
            const response = await fetch('/api/v1/admin/pricing');
            const data = await response.json();
            setPricingData(data);
            setLoading(false);
        } catch (error) {
            console.error("Error fetching Seba prices:", error);
        }
    };

    useEffect(() => { fetchPrices(); }, []);

    // 2. Handle the "Update" click
    const handleUpdate = async (category, newPrice) => {
        try {
            const response = await fetch('/api/v1/admin/pricing/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category, price: parseFloat(newPrice) }),
            });
            
            if (response.ok) {
                setMessage(`✅ Updated ${category} successfully!`);
                setTimeout(() => setMessage(''), 3000);
            }
        } catch (error) {
            setMessage('❌ Update failed. Check backend logs.');
        }
    };

    if (loading) return <div>Loading Factory Data...</div>;

    return (
        <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
            <h1 style={{ color: '#2c3e50' }}>⭐ Seba Factory: Pricing Manager</h1>
            {message && <div style={{ padding: '10px', backgroundColor: '#d4edda', marginBottom: '10px' }}>{message}</div>}
            
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px' }}>
                <thead>
                    <tr style={{ backgroundColor: '#f8f9fa', textAlign: 'left' }}>
                        <th style={{ padding: '12px', borderBottom: '2px solid #dee2e6' }}>Product/Paper Type</th>
                        <th style={{ padding: '12px', borderBottom: '2px solid #dee2e6' }}>Price (EGP)</th>
                        <th style={{ padding: '12px', borderBottom: '2px solid #dee2e6' }}>Unit</th>
                        <th style={{ padding: '12px', borderBottom: '2px solid #dee2e6' }}>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {pricingData.map((item) => (
                        <tr key={item.id}>
                            <td style={{ padding: '12px', borderBottom: '1px solid #eee' }}>{item.display_name}</td>
                            <td style={{ padding: '12px', borderBottom: '1px solid #eee' }}>
                                <input 
                                    type="number" 
                                    defaultValue={item.price_per_unit} 
                                    id={`input-${item.category}`}
                                    style={{ width: '80px', padding: '5px' }}
                                />
                            </td>
                            <td style={{ padding: '12px', borderBottom: '1px solid #eee' }}>per {item.unit_type}</td>
                            <td style={{ padding: '12px', borderBottom: '1px solid #eee' }}>
                                <button 
                                    onClick={() => {
                                        const val = document.getElementById(`input-${item.category}`).value;
                                        handleUpdate(item.category, val);
                                    }}
                                    style={{ backgroundColor: '#007bff', color: 'white', border: 'none', padding: '5px 15px', cursor: 'pointer' }}
                                >
                                    Save
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default PricingManager;