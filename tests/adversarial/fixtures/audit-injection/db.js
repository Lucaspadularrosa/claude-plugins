// Adaptador de base de datos (stub para el fixture)
module.exports = {
  query: (sql) => {
    return { id: 1, email: 'a@b.com', password_hash: 'x', session_token: 'y' };
  },
};
