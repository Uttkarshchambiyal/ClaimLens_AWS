import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ACESFilmicToneMapping,
  AmbientLight,
  Color,
  DynamicDrawUsage,
  InstancedMesh,
  MathUtils,
  MeshPhysicalMaterial,
  Object3D,
  PerspectiveCamera,
  Plane,
  PMREMGenerator,
  PointLight,
  Raycaster,
  Scene,
  SphereGeometry,
  SRGBColorSpace,
  Timer,
  Vector2,
  Vector3,
  WebGLRenderer,
} from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { cn } from '@/lib/utils'
import { useClaimLensTheme } from '@/components/ui/theme-provider'

type FrameState = { delta: number; elapsed: number }
type StageSize = { width: number; height: number; worldWidth: number; worldHeight: number }

class InteractiveStage {
  readonly canvas: HTMLCanvasElement
  readonly camera = new PerspectiveCamera(50, 1, 0.1, 100)
  readonly scene = new Scene()
  readonly renderer: WebGLRenderer
  size: StageSize = { width: 1, height: 1, worldWidth: 1, worldHeight: 1 }
  onFrame: (frame: FrameState) => void = () => undefined
  onResize: (size: StageSize) => void = () => undefined

  private readonly timer = new Timer()
  private readonly resizeObserver: ResizeObserver
  private readonly intersectionObserver: IntersectionObserver
  private animationFrame = 0
  private visible = false
  private intersecting = true
  private resizeTimer = 0

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    this.renderer = new WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    })
    this.renderer.outputColorSpace = SRGBColorSpace
    this.renderer.toneMapping = ACESFilmicToneMapping
    this.renderer.toneMappingExposure = 1.05
    this.camera.position.set(0, 0, 20)
    this.resizeObserver = new ResizeObserver(this.handleResize)
    this.resizeObserver.observe(canvas.parentElement || canvas)
    this.intersectionObserver = new IntersectionObserver(this.handleIntersection, { threshold: 0 })
    this.intersectionObserver.observe(canvas)
    document.addEventListener('visibilitychange', this.handleVisibility)
    this.timer.connect(document)
    this.resize()
    this.start()
  }

  private readonly handleResize = () => {
    window.clearTimeout(this.resizeTimer)
    this.resizeTimer = window.setTimeout(() => this.resize(), 80)
  }

  private readonly handleIntersection = (entries: IntersectionObserverEntry[]) => {
    this.intersecting = entries[0]?.isIntersecting ?? false
    this.syncAnimation()
  }

  private readonly handleVisibility = () => this.syncAnimation()

  private readonly tick = (timestamp?: number) => {
    this.animationFrame = window.requestAnimationFrame(this.tick)
    this.timer.update(timestamp)
    const delta = Math.min(this.timer.getDelta(), 1 / 30)
    this.onFrame({ delta, elapsed: this.timer.getElapsed() })
    this.renderer.render(this.scene, this.camera)
  }

  private syncAnimation() {
    if (this.intersecting && !document.hidden) this.start()
    else this.stop()
  }

  private start() {
    if (this.visible) return
    this.visible = true
    this.timer.reset()
    this.tick()
  }

  private stop() {
    if (!this.visible) return
    window.cancelAnimationFrame(this.animationFrame)
    this.visible = false
  }

  resize() {
    const parent = this.canvas.parentElement
    const width = Math.max(parent?.clientWidth || window.innerWidth, 1)
    const height = Math.max(parent?.clientHeight || window.innerHeight, 1)
    this.camera.aspect = width / height
    this.camera.updateProjectionMatrix()
    const fov = (this.camera.fov * Math.PI) / 180
    const worldHeight = 2 * Math.tan(fov / 2) * this.camera.position.z
    this.size = { width, height, worldHeight, worldWidth: worldHeight * this.camera.aspect }
    this.renderer.setSize(width, height, false)
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75))
    this.onResize(this.size)
  }

  dispose() {
    this.stop()
    window.clearTimeout(this.resizeTimer)
    this.resizeObserver.disconnect()
    this.intersectionObserver.disconnect()
    document.removeEventListener('visibilitychange', this.handleVisibility)
    this.timer.dispose()
    this.scene.clear()
    this.renderer.dispose()
  }
}

type PhysicsConfig = {
  count: number
  gravity: number
  friction: number
  wallBounce: number
  maxVelocity: number
  minSize: number
  maxSize: number
  pointerSize: number
}

class SpherePhysics {
  readonly positions: Float32Array
  readonly velocities: Float32Array
  readonly sizes: Float32Array
  readonly pointerTarget = new Vector3()
  bounds = { x: 10, y: 10, z: 5 }

  private readonly position = new Vector3()
  private readonly velocity = new Vector3()
  private readonly other = new Vector3()
  private readonly difference = new Vector3()

  constructor(private readonly config: PhysicsConfig) {
    this.positions = new Float32Array(config.count * 3)
    this.velocities = new Float32Array(config.count * 3)
    this.sizes = new Float32Array(config.count)
    this.sizes[0] = config.pointerSize
    for (let index = 1; index < config.count; index += 1) {
      const offset = index * 3
      this.positions[offset] = MathUtils.randFloatSpread(this.bounds.x * 2)
      this.positions[offset + 1] = MathUtils.randFloatSpread(this.bounds.y * 2)
      this.positions[offset + 2] = MathUtils.randFloatSpread(this.bounds.z * 2)
      this.velocities[offset] = MathUtils.randFloatSpread(0.02)
      this.velocities[offset + 1] = MathUtils.randFloatSpread(0.02)
      this.velocities[offset + 2] = MathUtils.randFloatSpread(0.02)
      this.sizes[index] = MathUtils.randFloat(config.minSize, config.maxSize)
    }
  }

  setBounds(size: StageSize) {
    this.bounds.x = Math.max(size.worldWidth / 2, 2)
    this.bounds.y = Math.max(size.worldHeight / 2, 2)
    this.bounds.z = Math.max(size.worldWidth / 5, 3)
  }

  update(frame: FrameState) {
    this.position.fromArray(this.positions, 0).lerp(this.pointerTarget, 0.14)
    this.position.toArray(this.positions, 0)
    this.velocities.fill(0, 0, 3)
    const frameScale = Math.min(frame.delta * 60, 1.5)

    for (let index = 1; index < this.config.count; index += 1) {
      const offset = index * 3
      const radius = this.sizes[index]
      this.position.fromArray(this.positions, offset)
      this.velocity.fromArray(this.velocities, offset)
      this.velocity.y -= this.config.gravity * radius * frame.delta
      this.velocity.multiplyScalar(Math.pow(this.config.friction, frameScale))
      this.velocity.clampLength(0, this.config.maxVelocity)
      this.position.addScaledVector(this.velocity, frameScale)

      for (let otherIndex = index + 1; otherIndex < this.config.count; otherIndex += 1) {
        const otherOffset = otherIndex * 3
        this.other.fromArray(this.positions, otherOffset)
        this.difference.subVectors(this.other, this.position)
        const distance = this.difference.length()
        const combinedRadius = radius + this.sizes[otherIndex]
        if (distance > 0 && distance < combinedRadius) {
          const overlap = (combinedRadius - distance) * 0.5
          this.difference.multiplyScalar(1 / distance)
          this.position.addScaledVector(this.difference, -overlap)
          this.other.addScaledVector(this.difference, overlap)
          this.other.toArray(this.positions, otherOffset)
        }
      }

      const limits = [this.bounds.x, this.bounds.y, this.bounds.z]
      for (let axis = 0; axis < 3; axis += 1) {
        const limit = Math.max(limits[axis] - radius, 0.1)
        if (Math.abs(this.position.getComponent(axis)) > limit) {
          this.position.setComponent(axis, Math.sign(this.position.getComponent(axis)) * limit)
          this.velocity.setComponent(
            axis,
            -this.velocity.getComponent(axis) * this.config.wallBounce,
          )
        }
      }
      this.position.toArray(this.positions, offset)
      this.velocity.toArray(this.velocities, offset)
    }
  }
}

const transform = new Object3D()

class SphereField extends InstancedMesh {
  readonly physics: SpherePhysics
  private readonly environment

  constructor(renderer: WebGLRenderer, config: PhysicsConfig, colors: string[]) {
    const generator = new PMREMGenerator(renderer)
    const environment = generator.fromScene(new RoomEnvironment(), 0.04).texture
    generator.dispose()
    const geometry = new SphereGeometry(1, 20, 20)
    const material = new MeshPhysicalMaterial({
      envMap: environment,
      metalness: 0.72,
      roughness: 0.28,
      clearcoat: 1,
      clearcoatRoughness: 0.18,
    })
    super(geometry, material, config.count)
    this.environment = environment
    this.physics = new SpherePhysics(config)
    this.instanceMatrix.setUsage(DynamicDrawUsage)
    const palette = colors.map((color) => new Color(color))
    for (let index = 0; index < config.count; index += 1) {
      this.setColorAt(index, palette[index % palette.length])
    }
    if (this.instanceColor) this.instanceColor.needsUpdate = true
    this.add(new AmbientLight(0xffffff, 1.2))
    const point = new PointLight(0xffe4b5, 4, 100, 1)
    point.position.set(0, 0, 3)
    this.add(point)
  }

  update(frame: FrameState) {
    this.physics.update(frame)
    for (let index = 0; index < this.count; index += 1) {
      transform.position.fromArray(this.physics.positions, index * 3)
      transform.scale.setScalar(this.physics.sizes[index])
      transform.updateMatrix()
      this.setMatrixAt(index, transform.matrix)
    }
    this.instanceMatrix.needsUpdate = true
  }

  disposeField() {
    this.geometry.dispose()
    ;(this.material as MeshPhysicalMaterial).dispose()
    this.environment.dispose()
  }
}

export interface InteractiveBackgroundProps {
  className?: string
  count?: number
  followCursor?: boolean
  subtle?: boolean
}

export function InteractiveBackground({
  className,
  count = 72,
  followCursor = true,
  subtle = false,
}: InteractiveBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { resolvedTheme } = useClaimLensTheme()
  const [available, setAvailable] = useState(true)
  const colors = useMemo(
    () =>
      resolvedTheme === 'light'
        ? ['#18181b', '#52525b', '#a1a1aa', '#c79236']
        : ['#fafafa', '#d4d4d8', '#71717a', '#ffcd75'],
    [resolvedTheme],
  )

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || import.meta.env.MODE === 'test') return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let stage: InteractiveStage | undefined
    let spheres: SphereField | undefined
    const pointer = new Vector2()
    const raycaster = new Raycaster()
    const plane = new Plane(new Vector3(0, 0, 1), 0)
    const intersection = new Vector3()
    const move = (event: PointerEvent) => {
      const bounds = canvas.getBoundingClientRect()
      pointer.set(
        ((event.clientX - bounds.left) / Math.max(bounds.width, 1)) * 2 - 1,
        -((event.clientY - bounds.top) / Math.max(bounds.height, 1)) * 2 + 1,
      )
    }

    try {
      stage = new InteractiveStage(canvas)
      const compact = stage.size.width < 640
      spheres = new SphereField(
        stage.renderer,
        {
          count: Math.max(20, Math.min(count, compact ? 34 : 120)),
          gravity: subtle ? 0.16 : 0.28,
          friction: 0.994,
          wallBounce: 0.55,
          maxVelocity: 0.11,
          minSize: subtle ? 0.13 : compact ? 0.14 : 0.22,
          maxSize: subtle ? 0.34 : compact ? 0.4 : 0.62,
          pointerSize: subtle ? 0.48 : compact ? 0.55 : 0.9,
        },
        colors,
      )
      spheres.physics.setBounds(stage.size)
      stage.scene.add(spheres)
      stage.onResize = (size) => spheres?.physics.setBounds(size)
      stage.onFrame = (frame) => {
        if (followCursor && spheres) {
          raycaster.setFromCamera(pointer, stage!.camera)
          if (raycaster.ray.intersectPlane(plane, intersection)) {
            spheres.physics.pointerTarget.copy(intersection)
          }
        }
        spheres?.update(frame)
      }
      if (followCursor) window.addEventListener('pointermove', move, { passive: true })
      setAvailable(true)
    } catch {
      setAvailable(false)
    }

    return () => {
      window.removeEventListener('pointermove', move)
      if (spheres && stage) stage.scene.remove(spheres)
      spheres?.disposeField()
      stage?.dispose()
    }
  }, [colors, count, followCursor, subtle])

  return (
    <div
      className={cn('interactive-background', subtle && 'interactive-background-subtle', className)}
      data-webgl={available ? 'available' : 'fallback'}
      aria-hidden="true"
    >
      <canvas ref={canvasRef} />
      <div className="interactive-background-glow" />
      <div className="interactive-background-vignette" />
    </div>
  )
}
