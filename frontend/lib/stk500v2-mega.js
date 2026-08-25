/**
 * Minimal STK500v2 programmer for Arduino Mega 2560 over Web Serial.
 * Protocol framing matches avrdude / Mega Optiboot-stk500v2 (115200).
 */
(function (root) {
  const MESSAGE_START = 0x1b;
  const TOKEN = 0x0e;
  const CMD_SIGN_ON = 0x01;
  const CMD_LOAD_ADDRESS = 0x06;
  const CMD_ENTER_PROGMODE_ISP = 0x10;
  const CMD_LEAVE_PROGMODE_ISP = 0x11;
  const CMD_PROGRAM_FLASH_ISP = 0x13;
  const STATUS_CMD_OK = 0x00;
  const PAGE_SIZE = 256;

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function parseIntelHex(text) {
    const mem = new Map();
    let ext = 0;
    let max = 0;
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim();
      if (!line.startsWith(":")) continue;
      const len = parseInt(line.slice(1, 3), 16);
      const addr = parseInt(line.slice(3, 7), 16);
      const type = parseInt(line.slice(7, 9), 16);
      if (type === 0) {
        const base = ext + addr;
        for (let i = 0; i < len; i++) {
          const b = parseInt(line.slice(9 + i * 2, 11 + i * 2), 16);
          mem.set(base + i, b);
          if (base + i > max) max = base + i;
        }
      } else if (type === 1) {
        break;
      } else if (type === 2) {
        ext = parseInt(line.slice(9, 13), 16) << 4;
      } else if (type === 4) {
        ext = parseInt(line.slice(9, 13), 16) << 16;
      }
    }
    const size = Math.ceil((max + 1) / PAGE_SIZE) * PAGE_SIZE;
    const buf = new Uint8Array(size || PAGE_SIZE);
    buf.fill(0xff);
    for (const [a, b] of mem) buf[a] = b;
    return buf;
  }

  function checksum(bytes) {
    let c = 0;
    for (const b of bytes) c ^= b;
    return c;
  }

  function frame(seq, body) {
    const len = body.length;
    const head = [MESSAGE_START, seq & 0xff, (len >> 8) & 0xff, len & 0xff, TOKEN];
    const msg = Uint8Array.from([...head, ...body, 0]);
    msg[msg.length - 1] = checksum(msg.subarray(0, msg.length - 1));
    return msg;
  }

  class StkSession {
    constructor(port) {
      this.port = port;
      this.writer = port.writable.getWriter();
      this.reader = port.readable.getReader();
      this.buf = new Uint8Array(0);
      this.seq = 1;
    }

    async close() {
      try {
        this.reader.releaseLock();
      } catch (_) {}
      try {
        this.writer.releaseLock();
      } catch (_) {}
      try {
        await this.port.close();
      } catch (_) {}
    }

    append(chunk) {
      const next = new Uint8Array(this.buf.length + chunk.length);
      next.set(this.buf);
      next.set(chunk, this.buf.length);
      this.buf = next;
    }

    async readByte(deadline) {
      while (this.buf.length < 1) {
        if (Date.now() > deadline) throw new Error("STK500v2: timed out waiting for data");
        const remain = Math.max(1, deadline - Date.now());
        const result = await Promise.race([
          this.reader.read(),
          sleep(remain).then(() => ({ timeout: true })),
        ]);
        if (result.timeout) throw new Error("STK500v2: timed out waiting for data");
        if (result.done) throw new Error("STK500v2: serial closed");
        if (result.value) this.append(result.value);
      }
      const b = this.buf[0];
      this.buf = this.buf.subarray(1);
      return b;
    }

    async readMessage(timeoutMs = 3000) {
      const deadline = Date.now() + timeoutMs;
      while ((await this.readByte(deadline)) !== MESSAGE_START) {
        /* resync */
      }
      const seq = await this.readByte(deadline);
      const lenHi = await this.readByte(deadline);
      const lenLo = await this.readByte(deadline);
      const token = await this.readByte(deadline);
      if (token !== TOKEN) throw new Error("STK500v2: bad token");
      const len = (lenHi << 8) | lenLo;
      const body = new Uint8Array(len);
      for (let i = 0; i < len; i++) body[i] = await this.readByte(deadline);
      const ck = await this.readByte(deadline);
      const chkInput = Uint8Array.from([
        MESSAGE_START,
        seq,
        lenHi,
        lenLo,
        TOKEN,
        ...body,
      ]);
      if (checksum(chkInput) !== ck) throw new Error("STK500v2: checksum mismatch");
      return body;
    }

    async cmd(body, timeoutMs = 3000) {
      const seq = this.seq++ & 0xff;
      await this.writer.write(frame(seq, body));
      const resp = await this.readMessage(timeoutMs);
      if (resp[0] !== body[0] || resp[1] !== STATUS_CMD_OK) {
        throw new Error(
          "STK500v2: command 0x" + body[0].toString(16) + " failed (status " + (resp[1] ?? "?") + ")"
        );
      }
      return resp;
    }
  }

  async function resetIntoBootloader(port) {
    await port.setSignals({ dataTerminalReady: false, requestToSend: false });
    await sleep(50);
    await port.setSignals({ dataTerminalReady: true, requestToSend: true });
    await sleep(250);
  }

  async function flashMega2560(hexText, opts = {}) {
    const onProgress = opts.onProgress || (() => {});
    if (!("serial" in navigator)) {
      throw new Error("Web Serial is not available");
    }
    const image = parseIntelHex(hexText);
    const serialPort = await navigator.serial.requestPort();
    await serialPort.open({ baudRate: opts.baudRate || 115200 });
    const session = new StkSession(serialPort);
    try {
      await resetIntoBootloader(serialPort);
      onProgress(1, "sync");
      await session.cmd([CMD_SIGN_ON], 4000);
      await session.cmd(
        Uint8Array.from([
          CMD_ENTER_PROGMODE_ISP,
          200,
          100,
          25,
          32,
          0,
          0x53,
          3,
          0xac,
          0x53,
          0,
          0,
        ])
      );
      const pages = image.length / PAGE_SIZE;
      for (let i = 0; i < pages; i++) {
        const addr = i * PAGE_SIZE;
        const page = image.subarray(addr, addr + PAGE_SIZE);
        if (page.every((b) => b === 0xff)) continue;
        const wordAddr = addr >> 1;
        await session.cmd(
          Uint8Array.from([
            CMD_LOAD_ADDRESS,
            (wordAddr >> 24) & 0xff,
            (wordAddr >> 16) & 0xff,
            (wordAddr >> 8) & 0xff,
            wordAddr & 0xff,
          ])
        );
        const body = new Uint8Array(10 + PAGE_SIZE);
        body.set([CMD_PROGRAM_FLASH_ISP, PAGE_SIZE >> 8, PAGE_SIZE & 0xff, 0xc1, 10, 0x40, 0x4c, 0x20, 0xff, 0xff]);
        body.set(page, 10);
        await session.cmd(body, 5000);
        onProgress(Math.round(((i + 1) / pages) * 100), "write");
      }
      await session.cmd(Uint8Array.from([CMD_LEAVE_PROGMODE_ISP, 1, 1]));
      onProgress(100, "done");
    } finally {
      await session.close();
    }
  }

  root.flashMega2560 = flashMega2560;
  root.parseIntelHex = parseIntelHex;
})(typeof window !== "undefined" ? window : globalThis);
