/**
 * three.js viewer for GLB/FBX files served by the art-hub dev endpoint.
 * Orbit controls, auto framing, animation playback (FBX/GLB clips),
 * wireframe and skeleton toggles. Loaded lazily (React.lazy) so three.js
 * stays out of the main admin bundle.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Checkbox, Progress, Select, Space, Typography } from 'antd';
import { PauseOutlined, CaretRightOutlined, AimOutlined } from '@ant-design/icons';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import type { FileRef } from '../../../../art-hub/types';
import { fileUrl, textureUrl } from '../api';
import { formatBytes, formatNumber } from '../format';

const { Text } = Typography;
const AUTOLOAD_LIMIT = 20 * 1024 * 1024;

interface Stats {
  triangles: number;
  meshes: number;
  bones: number;
  materials: number;
  size: THREE.Vector3;
}

interface Runtime {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  root?: THREE.Object3D;
  mixer?: THREE.AnimationMixer;
  clips: THREE.AnimationClip[];
  action?: THREE.AnimationAction;
  skeleton?: THREE.SkeletonHelper;
  frame: () => void;
}

function disposeObject(obj: THREE.Object3D) {
  obj.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    const mats = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : [];
    for (const m of mats) {
      for (const v of Object.values(m)) if (v instanceof THREE.Texture) v.dispose();
      m.dispose();
    }
  });
}

function collectStats(root: THREE.Object3D, size: THREE.Vector3): Stats {
  let triangles = 0;
  let meshes = 0;
  const bones = new Set<string>();
  const materials = new Set<string>();
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if ((mesh as THREE.Mesh).isMesh && mesh.geometry) {
      meshes++;
      const g = mesh.geometry;
      triangles += g.index ? g.index.count / 3 : (g.attributes.position?.count ?? 0) / 3;
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      mats.forEach((m) => m && materials.add(m.uuid));
    }
    // FBXLoader may instantiate the same bone once per skin — count unique names.
    if ((o as THREE.Bone).isBone) bones.add(o.name || o.uuid);
  });
  return { triangles: Math.round(triangles), meshes, bones: bones.size, materials: materials.size, size };
}

const ModelViewer: React.FC<{ file: FileRef; height?: number }> = ({ file, height = 460 }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const rt = useRef<Runtime | null>(null);
  const [confirmed, setConfirmed] = useState((file.bytes ?? 0) <= AUTOLOAD_LIMIT);
  const [progress, setProgress] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [stats, setStats] = useState<Stats>();
  const [clipNames, setClipNames] = useState<string[]>([]);
  const [clipIndex, setClipIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [wireframe, setWireframe] = useState(false);
  const [showBones, setShowBones] = useState(false);
  const [missingTextures, setMissingTextures] = useState(0);

  useEffect(() => {
    setConfirmed((file.bytes ?? 0) <= AUTOLOAD_LIMIT);
  }, [file.path, file.bytes]);

  // renderer lifecycle + loading
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !confirmed) return undefined;
    let disposed = false;
    setError(undefined);
    setStats(undefined);
    setClipNames([]);
    setClipIndex(0);
    setProgress(0);
    setMissingTextures(0);
    setLoading(true);

    const width = mount.clientWidth || 640;
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.borderRadius = '6px';
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#eef1f5');
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f98, 2.2));
    const key = new THREE.DirectionalLight(0xffffff, 2.4);
    key.position.set(3, 5, 4);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xffffff, 0.8);
    rim.position.set(-4, 3, -3);
    scene.add(rim);

    const camera = new THREE.PerspectiveCamera(40, width / height, 0.01, 1000);
    camera.position.set(1, 1, 2);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    let last = performance.now();
    const runtime: Runtime = {
      renderer,
      scene,
      camera,
      controls,
      clips: [],
      frame: () => {
        const now = performance.now();
        const dt = Math.min((now - last) / 1000, 0.1);
        last = now;
        runtime.mixer?.update(dt);
        controls.update();
        renderer.render(scene, camera);
      },
    };
    rt.current = runtime;
    renderer.setAnimationLoop(runtime.frame);

    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth || width;
      renderer.setSize(w, height);
      camera.aspect = w / height;
      camera.updateProjectionMatrix();
    });
    ro.observe(mount);

    const modelUrl = fileUrl(file);
    const manager = new THREE.LoadingManager();
    let missing = 0;
    manager.setURLModifier((url) => {
      if (url === modelUrl || url.startsWith('data:') || url.startsWith('blob:')) return url;
      return textureUrl(file.path, url);
    });
    const onProgress = (e: ProgressEvent) => {
      const total = e.total || file.bytes || 0;
      if (total > 0) setProgress(Math.min(100, Math.round((e.loaded / total) * 100)));
    };

    const load: Promise<{ root: THREE.Object3D; clips: THREE.AnimationClip[] }> =
      file.kind === 'fbx'
        ? new FBXLoader(manager).loadAsync(modelUrl, onProgress).then((g) => ({ root: g, clips: g.animations ?? [] }))
        : new GLTFLoader(manager).loadAsync(modelUrl, onProgress).then((g) => ({ root: g.scene, clips: g.animations ?? [] }));

    load
      .then(async ({ root, clips }) => {
        if (disposed) {
          disposeObject(root);
          return;
        }
        // frame the model: bottom on the grid, centred on X/Z
        const box = new THREE.Box3().setFromObject(root);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        root.position.sub(new THREE.Vector3(center.x, box.min.y, center.z));
        scene.add(root);
        const maxDim = Math.max(size.x, size.y, size.z) || 1;
        const grid = new THREE.GridHelper(maxDim * 2.5, 10, 0x9aa3ad, 0xd0d5dc);
        scene.add(grid);
        const dist = (maxDim / (2 * Math.tan((camera.fov * Math.PI) / 360))) * 1.35;
        camera.near = maxDim / 200;
        camera.far = maxDim * 200;
        camera.position.set(dist * 0.55, size.y * 0.6 + dist * 0.25, dist);
        camera.updateProjectionMatrix();
        controls.target.set(0, size.y * 0.5, 0);
        controls.update();

        runtime.root = root;
        runtime.clips = clips;
        if (clips.length) {
          runtime.mixer = new THREE.AnimationMixer(root);
          runtime.action = runtime.mixer.clipAction(clips[0]!);
          runtime.action.play();
        }
        const skel = new THREE.SkeletonHelper(root);
        skel.visible = false;
        scene.add(skel);
        runtime.skeleton = skel;

        setStats(collectStats(root, size));
        setClipNames(clips.map((c, i) => `${c.name || `клип ${i + 1}`} · ${c.duration.toFixed(2)} с`));
        setPlaying(true);
        // detect placeholder textures (HEAD is cheap; only for FBX)
        if (file.kind === 'fbx') {
          const urls = new Set<string>();
          root.traverse((o) => {
            const mesh = o as THREE.Mesh;
            const mats = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : [];
            for (const m of mats) {
              for (const v of Object.values(m)) {
                if (v instanceof THREE.Texture) {
                  const src = (v.image as HTMLImageElement | undefined)?.src;
                  if (src && src.includes('/__art-hub/texture')) urls.add(src);
                }
              }
            }
          });
          for (const u of urls) {
            try {
              const r = await fetch(u, { method: 'HEAD' });
              if (r.headers.get('X-Art-Hub-Missing') === '1') missing++;
            } catch {
              /* ignore */
            }
          }
          if (!disposed) setMissingTextures(missing);
        }
      })
      .catch((err: unknown) => {
        if (!disposed) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });

    return () => {
      disposed = true;
      ro.disconnect();
      renderer.setAnimationLoop(null);
      controls.dispose();
      if (runtime.root) disposeObject(runtime.root);
      runtime.skeleton?.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      rt.current = null;
    };
    // Reload only when the file itself changes (auto-refresh creates new FileRef objects).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file.path, file.mtime, file.kind, confirmed, height]);

  // clip switching / play-pause
  useEffect(() => {
    const r = rt.current;
    if (!r?.mixer || !r.clips.length) return;
    const clip = r.clips[clipIndex];
    if (!clip) return;
    r.mixer.stopAllAction();
    r.action = r.mixer.clipAction(clip);
    r.action.play();
    r.action.paused = !playing;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clipIndex]);

  useEffect(() => {
    const r = rt.current;
    if (r?.action) r.action.paused = !playing;
  }, [playing]);

  useEffect(() => {
    rt.current?.root?.traverse((o) => {
      const mesh = o as THREE.Mesh;
      const mats = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : [];
      mats.forEach((m) => {
        if ('wireframe' in m) (m as THREE.MeshStandardMaterial).wireframe = wireframe;
      });
    });
  }, [wireframe, stats]);

  useEffect(() => {
    if (rt.current?.skeleton) rt.current.skeleton.visible = showBones;
  }, [showBones, stats]);

  const resetView = () => {
    const r = rt.current;
    if (!r || !stats) return;
    const maxDim = Math.max(stats.size.x, stats.size.y, stats.size.z) || 1;
    const dist = (maxDim / (2 * Math.tan((r.camera.fov * Math.PI) / 360))) * 1.35;
    r.camera.position.set(dist * 0.55, stats.size.y * 0.6 + dist * 0.25, dist);
    r.controls.target.set(0, stats.size.y * 0.5, 0);
    r.controls.update();
  };

  if (!confirmed) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#eef1f5', borderRadius: 6 }}>
        <Space direction="vertical" align="center">
          <Text>Модель большая ({formatBytes(file.bytes)}) — загрузка может занять время и память GPU.</Text>
          <Button type="primary" onClick={() => setConfirmed(true)}>
            Загрузить модель
          </Button>
        </Space>
      </div>
    );
  }

  return (
    <div data-testid="art-hub-model-viewer">
      <div style={{ position: 'relative' }}>
        <div ref={mountRef} style={{ width: '100%', height, background: '#eef1f5', borderRadius: 6 }} />
        {loading ? (
          <div style={{ position: 'absolute', left: 16, right: 16, bottom: 16 }}>
            <Progress percent={progress} size="small" status="active" />
          </div>
        ) : null}
      </div>
      {error ? <Alert style={{ marginTop: 8 }} type="error" showIcon message={`Не удалось загрузить модель: ${error}`} /> : null}
      <Space wrap style={{ marginTop: 8, display: 'flex' }} size={[12, 4]}>
        {stats ? (
          <Text type="secondary" style={{ fontSize: 12 }}>
            треугольников {formatNumber(stats.triangles)} · мешей {stats.meshes} · материалов {stats.materials} · костей {stats.bones} · габарит{' '}
            {stats.size.x.toFixed(2)}×{stats.size.y.toFixed(2)}×{stats.size.z.toFixed(2)} (ед. файла)
          </Text>
        ) : null}
        {missingTextures > 0 ? (
          <Text type="warning" style={{ fontSize: 12 }}>
            текстур не найдено рядом с файлом: {missingTextures} (показана серая заглушка)
          </Text>
        ) : null}
      </Space>
      <Space wrap style={{ marginTop: 6, display: 'flex' }}>
        {clipNames.length ? (
          <>
            <Select
              size="small"
              style={{ minWidth: 220 }}
              value={clipIndex}
              onChange={setClipIndex}
              options={clipNames.map((n, i) => ({ value: i, label: n }))}
            />
            <Button size="small" icon={playing ? <PauseOutlined /> : <CaretRightOutlined />} onClick={() => setPlaying((p) => !p)}>
              {playing ? 'пауза' : 'играть'}
            </Button>
          </>
        ) : stats ? (
          <Text type="secondary" style={{ fontSize: 12 }}>
            анимаций в файле нет
          </Text>
        ) : null}
        <Checkbox checked={wireframe} onChange={(e) => setWireframe(e.target.checked)}>
          сетка
        </Checkbox>
        <Checkbox checked={showBones} onChange={(e) => setShowBones(e.target.checked)} disabled={!stats?.bones}>
          кости
        </Checkbox>
        <Button size="small" icon={<AimOutlined />} onClick={resetView} disabled={!stats}>
          вид по умолчанию
        </Button>
      </Space>
    </div>
  );
};

export default ModelViewer;
