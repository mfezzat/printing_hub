// Simple React Logic for your Panel
const AdminPricing = () => {
    const [prices, setPrices] = useState([]);

    const handleUpdate = async (category, val) => {
        await fetch('/api/v1/admin/pricing/update', {
            method: 'POST',
            body: JSON.stringify({ category, new_price: parseFloat(val) })
        });
        alert("Price Saved for Seba Factory!");
    };

    return (
        <div className="p-6 bg-white rounded shadow">
            <h2>💰 Factory Pricing Manager</h2>
            {prices.map(p => (
                <div key={p.category} className="flex gap-4 mb-2">
                    <span>{p.display_name}</span>
                    <input 
                        type="number" 
                        defaultValue={p.price_per_unit} 
                        onBlur={(e) => handleUpdate(p.category, e.target.value)}
                    />
                    <span>EGP per {p.unit_type}</span>
                </div>
            ))}
        </div>
    );
};