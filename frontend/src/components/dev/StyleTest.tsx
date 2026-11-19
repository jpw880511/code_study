import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

// Development-only sections for checking Tailwind CSS and shadcn/ui by eye. Not product UI.

const SAMPLE_CLASSES = ['bg-blue-500', 'text-white', 'p-4', 'rounded-lg']

const CLASS_EXPLANATIONS = [
  {
    className: 'bg-blue-500',
    description:
      '배경색을 파란색(blue-500)으로 지정합니다. 이 프로젝트의 Tailwind 4 값은 oklch(62.3% 0.214 259.815)입니다.',
  },
  { className: 'text-white', description: '글자색을 흰색(#fff)으로 지정합니다.' },
  {
    className: 'p-4',
    description: '사방의 안쪽 여백(padding)을 1rem(16px)으로 지정합니다. (간격 단위 0.25rem × 4)',
  },
  {
    className: 'rounded-lg',
    description: '모서리를 둥글게 합니다. 이 프로젝트의 테마에서는 0.625rem(10px)입니다.',
  },
]

export function TailwindClassTest() {
  return (
    <div className="space-y-3">
      <div data-testid="tailwind-sample" className={SAMPLE_CLASSES.join(' ')}>
        샘플 상자
      </div>
      <ul className="space-y-1 text-sm">
        {CLASS_EXPLANATIONS.map(({ className, description }) => (
          <li key={className}>
            <code className="rounded bg-muted px-1">{className}</code> <span>{description}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const BUTTON_VARIANTS = ['default', 'outline', 'ghost'] as const

export function ShadcnButtonTest() {
  return (
    <div className="flex flex-wrap gap-2">
      {BUTTON_VARIANTS.map((variant) => (
        <Button key={variant} variant={variant} onClick={() => window.alert(variant)}>
          {variant}
        </Button>
      ))}
    </div>
  )
}

export function ResponsiveGridTest() {
  return (
    <div className="space-y-3">
      <ul className="text-sm">
        <li>모바일(기본): 1열</li>
        <li>태블릿(md, 768px 이상): 2열</li>
        <li>데스크톱(lg, 1024px 이상): 3열</li>
      </ul>
      <div
        data-testid="responsive-grid"
        className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
      >
        {[1, 2, 3].map((number) => (
          <Card key={number} role="article">
            <CardHeader>
              <CardTitle>카드 {number}</CardTitle>
            </CardHeader>
            <CardContent>화면 폭에 따라 한 줄에 놓이는 카드 수가 바뀝니다.</CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
