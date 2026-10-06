import { afterEach, describe, expect, it } from 'vitest'

import { registry } from '@/contrib/registry'

import { COMPOSER_AREAS, type ComposerMiddleware, runComposerMiddleware } from './contrib'

const disposers: Array<() => void> = []

function addMiddleware(id: string, handler: ComposerMiddleware['handler'], order?: number) {
  disposers.push(
    registry.register({ id, area: COMPOSER_AREAS.middleware, order, data: { handler } satisfies ComposerMiddleware })
  )
}

afterEach(() => {
  disposers.splice(0).forEach(d => d())
})

describe('runComposerMiddleware', () => {
  it('passes the draft through untouched when nothing is registered', async () => {
    const draft = { text: 'hello' }

    expect(await runComposerMiddleware(draft)).toBe(draft)
  })

  it('chains rewrites in registry order', async () => {
    addMiddleware('b', d => ({ ...d, text: `${d.text}b` }), 20)
    addMiddleware('a', d => ({ ...d, text: `${d.text}a` }), 10)

    expect(await runComposerMiddleware({ text: 'x' })).toEqual({ text: 'xab' })
  })

  it('cancels the send when a handler returns null', async () => {
    addMiddleware('gate', () => null)
    addMiddleware('later', d => ({ ...d, text: 'never' }), 99)

    expect(await runComposerMiddleware({ text: 'x' })).toBeNull()
  })

  it('treats a throwing handler as pass-through', async () => {
    addMiddleware('boom', () => {
      throw new Error('broken plugin')
    })
    addMiddleware('after', d => ({ ...d, text: `${d.text}!` }), 99)

    expect(await runComposerMiddleware({ text: 'x' })).toEqual({ text: 'x!' })
  })

  it('supports async handlers', async () => {
    addMiddleware('async', async d => ({ ...d, text: d.text.toUpperCase() }))

    expect(await runComposerMiddleware({ text: 'quiet' })).toEqual({ text: 'QUIET' })
  })
})

describe('COMPOSER_AREAS.tray (plugin SDK accumulation area)', () => {
  it('exposes a composer.tray render area key', () => {
    expect(COMPOSER_AREAS.tray).toBe('composer.tray')
  })

  it('is distinct from the other composer render areas', () => {
    const renderAreas = new Set([
      COMPOSER_AREAS.top,
      COMPOSER_AREAS.bottom,
      COMPOSER_AREAS.underside,
      COMPOSER_AREAS.leading,
      COMPOSER_AREAS.actions,
      COMPOSER_AREAS.tray
    ])

    expect(renderAreas.size).toBe(6)
  })

  it('routes a registered render contribution through the registry by area', () => {
    expect(registry.getArea(COMPOSER_AREAS.tray)).toHaveLength(0)

    const dispose = registry.register({
      id: 'deploy-run-row',
      area: COMPOSER_AREAS.tray,
      render: () => 'running'
    })

    const contributions = registry.getArea(COMPOSER_AREAS.tray)

    expect(contributions).toHaveLength(1)
    expect(contributions[0].id).toBe('deploy-run-row')

    dispose()
    expect(registry.getArea(COMPOSER_AREAS.tray)).toHaveLength(0)
  })
})
