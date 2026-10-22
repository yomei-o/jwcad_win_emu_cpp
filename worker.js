// The emulator's thread.  It never returns from jwemu_main while Jw_cad runs:
// waiting for input is an Atomics.wait on the event ring the page fills.
importScripts('jwemu.js');

self.onmessage = async (msg) => {
    const m = msg.data;
    if (m.type !== 'start') return;
    const Module = await createJwemu({
        print: (s) => postMessage({type: 'log', text: s}),
        printErr: (s) => postMessage({type: 'log', text: s}),
        locateFile: (p) => p,
        setStatus: (s) => { if (s) postMessage({type: 'status', text: s}); },
    });
    Module.jwEvents = new Int32Array(m.events);
    const FS = Module.FS;
    try { FS.mkdir('/persist'); } catch (e) {}
    // Settings (the registry file) come from the page's localStorage.
    if (m.registry) FS.writeFile('/persist/registry.txt', m.registry);
    FS.chdir('/C:/jww');
    postMessage({type: 'status', text: 'running'});
    Module._jwemu_main(m.width, m.height);
};
