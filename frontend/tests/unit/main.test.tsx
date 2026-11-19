import { useQueryClient } from '@tanstack/react-query'
import { screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import { queryClient } from '../../src/lib/queryClient'

vi.mock('../../src/App', () => ({
  default: function Probe() {
    const client = useQueryClient()
    return <p>{client === queryClient ? 'shared client provided' : 'wrong client'}</p>
  },
}))

it('mounts the app inside the shared QueryClientProvider', async () => {
  document.body.innerHTML = '<div id="root"></div>'
  await import('../../src/main')
  expect(await screen.findByText('shared client provided')).toBeInTheDocument()
})
