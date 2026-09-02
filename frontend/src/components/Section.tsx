import type { ReactNode } from 'react'

export default function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-gray-200 p-5 dark:border-gray-800">
      <h2 className="mb-4 text-base font-semibold text-gray-900 dark:text-gray-100">{title}</h2>
      {children}
    </section>
  )
}
