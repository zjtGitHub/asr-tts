const WebSocket = require('ws');
const { handleBuffer } = require('./test_vad_microphone');

const server = new WebSocket.Server({ port: 8080 });

server.on('connection', (ws) => {
  console.log('Client connected');

  // 当接收到客户端消息时
  ws.on('message', (message) => {
    console.log('Received:', message);
    const audio = handleBuffer(message)
    ws.send(audio);
  });

  // 当客户端断开连接时
  ws.on('close', () => {
    console.log('Client disconnected');
  });

  // 发送欢迎消息
  ws.send('Welcome to the WebSocket server');
});

console.log('WebSocket server is running on ws://localhost:8080');