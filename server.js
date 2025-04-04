const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const path = require('path');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(bodyParser.json());
app.use(express.static('public'));

// In-memory storage (replace with database in production)
let menuItems = [
    {
        id: 1,
        category: 'Beverages',
        name: 'Espresso',
        price: 3.50,
        description: 'Rich and bold single shot espresso'
    },
    {
        id: 2,
        category: 'Pastries',
        name: 'Croissant',
        price: 3.00,
        description: 'Buttery, flaky French-style croissant'
    }
];

let categories = ['Beverages', 'Pastries', 'Sandwiches', 'Desserts'];

// Admin credentials (replace with proper authentication in production)
const ADMIN_USERNAME = 'admin';
const ADMIN_PASSWORD = 'admin123';

// Routes
app.get('/api/menu', (req, res) => {
    res.json(menuItems);
});

app.get('/api/categories', (req, res) => {
    res.json(categories);
});

// Admin routes
app.post('/api/admin/login', (req, res) => {
    const { username, password } = req.body;
    if (username === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
        const token = jwt.sign({ username }, 'your-secret-key', { expiresIn: '1h' });
        res.json({ token });
    } else {
        res.status(401).json({ error: 'Invalid credentials' });
    }
});

app.post('/api/admin/menu', (req, res) => {
    const { token } = req.headers;
    if (!token) {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    try {
        jwt.verify(token, 'your-secret-key');
        const newItem = {
            id: menuItems.length + 1,
            ...req.body
        };
        menuItems.push(newItem);
        res.json(newItem);
    } catch (error) {
        res.status(401).json({ error: 'Invalid token' });
    }
});

app.put('/api/admin/menu/:id', (req, res) => {
    const { token } = req.headers;
    if (!token) {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    try {
        jwt.verify(token, 'your-secret-key');
        const id = parseInt(req.params.id);
        const index = menuItems.findIndex(item => item.id === id);
        if (index !== -1) {
            menuItems[index] = { ...menuItems[index], ...req.body };
            res.json(menuItems[index]);
        } else {
            res.status(404).json({ error: 'Item not found' });
        }
    } catch (error) {
        res.status(401).json({ error: 'Invalid token' });
    }
});

app.delete('/api/admin/menu/:id', (req, res) => {
    const { token } = req.headers;
    if (!token) {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    try {
        jwt.verify(token, 'your-secret-key');
        const id = parseInt(req.params.id);
        menuItems = menuItems.filter(item => item.id !== id);
        res.json({ success: true });
    } catch (error) {
        res.status(401).json({ error: 'Invalid token' });
    }
});

// Serve admin page
app.get('/admin', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
}); 