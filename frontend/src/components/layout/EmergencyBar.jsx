import { PhoneCall } from 'lucide-react'

export default function EmergencyBar() {
  return (
    <div className="bg-clay-700 text-clay-100">
      <div className="mx-auto flex max-w-5xl items-center justify-center gap-2 px-4 py-2 text-center text-sm">
        <PhoneCall size={15} className="shrink-0" aria-hidden="true" />
        <p>
          <span className="font-medium">Em perigo agora?</span> Ligue{' '}
          <a href="tel:190" className="underline decoration-clay-100/50 underline-offset-2 hover:decoration-clay-100">
            190
          </a>{' '}
          (Polícia) ou{' '}
          <a href="tel:180" className="underline decoration-clay-100/50 underline-offset-2 hover:decoration-clay-100">
            180
          </a>{' '}
          (Central de Atendimento à Mulher, sigiloso, 24h).
        </p>
      </div>
    </div>
  )
}