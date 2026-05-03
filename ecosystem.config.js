module.exports = {
  apps: [
    {
      name: "ege-docs",
      script: "/root/ege_master1/.venv/bin/python3",
      args: "-m uvicorn app.main:app --host 0.0.0.0 --port 9050",
      cwd: "/root/ege_master1",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      watch: false,
      env: {
        NODE_ENV: "production",
      },
    },
  ],
};
