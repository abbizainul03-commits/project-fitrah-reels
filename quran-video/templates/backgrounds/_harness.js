// Tiny WebGL2 harness shared by the generated backgrounds.
// A page defines `const FRAG = \`...\`` (GLSL ES 3.0 body using uniforms below) and includes this file.
//   uniform vec2  uRes;   // canvas size in px
//   uniform float uTime;  // seconds, 0..uLoop
//   uniform float uLoop;  // loop length in seconds (animation must be seamless at uLoop)
// The renderer calls window.drawFrame(t, loop) for each frame, then screenshots.
(function () {
  const canvas = document.getElementById('c');
  const gl = canvas.getContext('webgl2', { preserveDrawingBuffer: true, antialias: false });
  if (!gl) { document.body.innerHTML = 'WebGL2 not available'; return; }
  const vs = `#version 300 es
  in vec2 p; void main(){ gl_Position = vec4(p,0.,1.); }`;
  const fs = `#version 300 es
  precision highp float;
  uniform vec2 uRes; uniform float uTime; uniform float uLoop;
  out vec4 outColor;
  #define TAU 6.28318530718
  float hash(vec2 p){ p = fract(p*vec2(123.34, 456.21)); p += dot(p, p+45.32); return fract(p.x*p.y); }
  float noise(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.-2.*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),u.x), mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),u.x), u.y); }
  float fbm(vec2 p){ float v=0., a=.5; mat2 r=mat2(.8,.6,-.6,.8); for(int i=0;i<6;i++){ v+=a*noise(p); p=r*p*2.02+17.1; a*=.5; } return v; }
  ${window.FRAG}`;
  function sh(type, src) {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }
  const prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(prog); gl.useProgram(prog);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const uRes = gl.getUniformLocation(prog, 'uRes'), uTime = gl.getUniformLocation(prog, 'uTime'), uLoop = gl.getUniformLocation(prog, 'uLoop');
  window.drawFrame = function (t, loop) {
    canvas.width = window.innerWidth; canvas.height = window.innerHeight;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(uRes, canvas.width, canvas.height); gl.uniform1f(uTime, t); gl.uniform1f(uLoop, loop);
    gl.drawArrays(gl.TRIANGLES, 0, 3); gl.finish();
    return true;
  };
  window.drawFrame(0, 16);
})();
