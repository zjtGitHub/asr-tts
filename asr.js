// Copyright (c)  2023-2024  Xiaomi Corporation (authors: Fangjun Kuang)
//
const WebSocket = require('ws');
const sherpa_onnx = require('sherpa-onnx-node');

// 创建识别器
function createRecognizer() {
  const config = {
    'featConfig': {
      'sampleRate': 16000,
      'featureDim': 80,
    },
    'modelConfig': {
      'paraformer': {
        'model': './sherpa-onnx-paraformer-zh-2023-09-14/model.int8.onnx',
      },
      'tokens': './sherpa-onnx-paraformer-zh-2023-09-14/tokens.txt',
      'numThreads': 2,
      'provider': 'cpu',
      'debug': 1,
    }
  };

  return new sherpa_onnx.OfflineRecognizer(config);
}

// 创建 VAD
function createVad() {
  const config = {
    sileroVad: {
      model: './silero_vad.onnx',
      threshold: 0.5,
      minSpeechDuration: 0.25,
      minSilenceDuration: 0.5,
      windowSize: 512,
    },
    sampleRate: 16000,
    debug: true,
    numThreads: 1,
  };

  const bufferSizeInSeconds = 60;

  return new sherpa_onnx.Vad(config, bufferSizeInSeconds);
}

const recognizer = createRecognizer();
const vad = createVad();

const bufferSizeInSeconds = 30;
const buffer =
    new sherpa_onnx.CircularBuffer(bufferSizeInSeconds * vad.config.sampleRate);

// 创建 WebSocket 服务器
const wss = new WebSocket.Server({ port: 8080 });

let printed = false;
let index = 0;

wss.on('connection', (ws) => {
  console.log('connected');
  ws.on('message', (data) => {
    console.log(data, 'data');
    const floatData = new Float32Array(data);
    const windowSize = vad.config.sileroVad.windowSize;
    buffer.push(floatData);
    vad.acceptWaveform(buffer);
    if (vad.isDetected() && !printed) {
      console.log(`${index}: Detected speech`)
      printed = true;
    }

    if (!vad.isDetected()) {
      printed = false;
    }
    console.log(vad.isEmpty(), 'vad.isEmpty()');
    while (!vad.isEmpty()) {
      const segment = vad.front();
      const stream = recognizer.createStream();
      stream.acceptWaveform({
        samples: segment.samples,
        sampleRate: recognizer.config.featConfig.sampleRate
      });
      recognizer.decode(stream);
      const r = recognizer.getResult(stream);
      if (r.text.length > 0) {
        const text = r.text.toLowerCase().trim();
        console.log(`${index}: ${text}`);

        const filename = `${index}-${text}-${
            new Date()
                .toLocaleTimeString('en-US', {hour12: false})
                .split(' ')[0]}.wav`;
        sherpa_onnx.writeWave(
            filename,
            {samples: segment.samples, sampleRate: vad.config.sampleRate});

        index += 1;
      }
    }
  });
});

console.log('WebSocket server started on port 8080. Please connect and send audio data.');
