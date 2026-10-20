// Where the API lives. Empty = same origin (local uvicorn serves both).
// scripts/deploy.sh overwrites this file with the API Gateway URL and the
// Cognito user pool client, e.g.
//   window.AUTH = { mode: "cognito", region: "us-east-1", clientId: "..." };
window.API_BASE = "";
window.AUTH = { mode: "local" }; // built-in accounts for local development
