INSERT INTO bs_users (username, password_hash, email, first_name, last_name, role)
SELECT 'manager', '$2b$12$Qswre5fNQ45ffX0q0I2ADOyTXsVig8Z4bcVilu2nCkF4RkoYlaOKW', 'manager@bookstore.local', 'Store', 'Manager', 'MANAGER'
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM bs_users WHERE username = 'manager' LIMIT 1);
