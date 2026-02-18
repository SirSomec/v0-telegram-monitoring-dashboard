import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  Search,
  Hash,
  Brain,
  Bell,
  UserPlus,
  Code2,
  Check,
  ArrowRight,
  MessageSquare,
  Star,
  Zap,
} from "lucide-react"

const features = [
  {
    icon: Search,
    title: "Мониторинг в реальном времени",
    description: "Отслеживайте упоминания в тысячах Telegram-групп мгновенно, 24/7 без перерывов.",
  },
  {
    icon: Hash,
    title: "Ключевые слова",
    description: "Настройте до 100 ключевых слов и фраз для точного мониторинга вашей ниши.",
  },
  {
    icon: Brain,
    title: "ИИ-анализ",
    description: "Семантический поиск на базе ИИ находит релевантные упоминания даже с синонимами.",
  },
  {
    icon: Bell,
    title: "Мгновенные уведомления",
    description: "Получайте оповещения в Telegram, на email или через Webhook в момент упоминания.",
  },
  {
    icon: UserPlus,
    title: "Сбор лидов",
    description: "Автоматически находите потенциальных клиентов и сохраняйте их в CRM.",
  },
  {
    icon: Code2,
    title: "API-доступ",
    description: "Полноценный REST API для интеграции с вашими системами и автоматизации.",
  },
]

const plans = [
  {
    name: "Стартовый",
    price: "1 490",
    period: "/мес",
    description: "Для начинающих и фрилансеров",
    features: ["5 ключевых слов", "10 групп", "Email-уведомления", "История за 7 дней", "Базовая аналитика"],
    popular: false,
  },
  {
    name: "Про",
    price: "3 990",
    period: "/мес",
    description: "Для растущих команд и агентств",
    features: [
      "25 ключевых слов",
      "Безлимит групп",
      "Уведомления в реальном времени",
      "История за 30 дней",
      "ИИ семантический поиск",
      "Трекинг лидов",
    ],
    popular: true,
  },
  {
    name: "Бизнес",
    price: "9 990",
    period: "/мес",
    description: "Для крупных компаний и enterprise",
    features: [
      "Безлимит ключевых слов",
      "Безлимит групп",
      "Приоритетная поддержка",
      "История за 365 дней",
      "API-доступ",
      "Кастомные интеграции",
      "Персональный менеджер",
    ],
    popular: false,
  },
]

const testimonials = [
  {
    name: "Алексей Петров",
    role: "CEO, CryptoAgency",
    initials: "АП",
    text: "TeleScope полностью изменил наш подход к лидогенерации. За первый месяц мы нашли 200+ горячих лидов из Telegram-групп.",
    rating: 5,
  },
  {
    name: "Мария Иванова",
    role: "Head of Marketing, FinTech",
    initials: "МИ",
    text: "Раньше мы тратили часы на ручной мониторинг. Теперь ИИ делает всё за нас. ROI окупился в первую неделю.",
    rating: 5,
  },
  {
    name: "Дмитрий Козлов",
    role: "Фрилансер, SMM",
    initials: "ДК",
    text: "Удобный интерфейс, быстрые уведомления и отличная поддержка. Рекомендую всем, кто работает с Telegram.",
    rating: 5,
  },
]

const faqItems = [
  {
    question: "Как TeleScope находит упоминания в Telegram?",
    answer: "Наш сервис использует легальный API Telegram для мониторинга публичных групп и каналов. Мы анализируем сообщения в реальном времени и сопоставляем их с вашими ключевыми словами.",
  },
  {
    question: "Сколько групп можно отслеживать одновременно?",
    answer: "На тарифе Стартовый - до 10 групп, на Про - безлимит, на Бизнес - безлимит с приоритетной обработкой. Можно добавлять любые публичные группы и каналы.",
  },
  {
    question: "Что такое ИИ семантический поиск?",
    answer: "Обычный поиск находит только точные совпадения. ИИ-поиск понимает контекст и синонимы. Например, если вы ищете 'крипто биржа', он также найдёт 'обмен криптовалюты', 'торговля биткоином' и т.д.",
  },
  {
    question: "Можно ли интегрировать TeleScope с CRM?",
    answer: "Да, на тарифе Бизнес доступен REST API, через который можно подключить любую CRM-систему. Также поддерживаются Webhook-уведомления для автоматизации через Zapier, Make и другие платформы.",
  },
  {
    question: "Есть ли бесплатный пробный период?",
    answer: "Да, мы предоставляем 7 дней бесплатного доступа ко всем функциям тарифа Про. Без привязки карты. Просто зарегистрируйтесь и начните мониторинг.",
  },
  {
    question: "Как быстро приходят уведомления?",
    answer: "На тарифах Про и Бизнес уведомления приходят мгновенно (в течение 5-10 секунд). На Стартовом тарифе - сводка каждые 15 минут на email.",
  },
]

const metrics = [
  { value: "10,000+", label: "Групп отслеживается" },
  { value: "1M+", label: "Упоминаний найдено" },
  { value: "5,000+", label: "Активных пользователей" },
  { value: "99.9%", label: "Аптайм сервиса" },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Navigation */}
      <nav className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-primary-foreground">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span className="text-lg font-bold tracking-tight">TeleScope</span>
          </div>

          <div className="hidden items-center gap-8 md:flex">
            <a href="#features" className="text-sm text-muted-foreground transition-colors hover:text-foreground">Возможности</a>
            <a href="#pricing" className="text-sm text-muted-foreground transition-colors hover:text-foreground">Тарифы</a>
            <a href="#testimonials" className="text-sm text-muted-foreground transition-colors hover:text-foreground">Отзывы</a>
            <a href="#faq" className="text-sm text-muted-foreground transition-colors hover:text-foreground">FAQ</a>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/auth">
              <Button variant="ghost" className="text-sm text-muted-foreground hover:text-foreground">
                Войти
              </Button>
            </Link>
            <Link href="/auth?tab=register">
              <Button className="bg-primary text-sm text-primary-foreground hover:bg-primary/90">
                Регистрация
              </Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden py-20 lg:py-32">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,oklch(0.62_0.18_250/0.15),transparent_60%)]" />
        <div className="relative mx-auto max-w-6xl px-4 text-center lg:px-6">
          <Badge variant="outline" className="mb-6 border-primary/30 bg-primary/10 text-primary">
            <Zap className="mr-1.5 size-3" />
            7 дней бесплатно -- без карты
          </Badge>

          <h1 className="mx-auto max-w-4xl text-balance text-4xl font-bold tracking-tight lg:text-6xl">
            Мониторинг Telegram{" "}
            <span className="bg-gradient-to-r from-primary to-[oklch(0.70_0.17_280)] bg-clip-text text-transparent">
              в реальном времени
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground">
            Отслеживайте упоминания вашего бренда, конкурентов и ключевых слов в тысячах Telegram-групп. Находите горячих лидов автоматически с помощью ИИ.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link href="/auth?tab=register">
              <Button size="lg" className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
                Начать бесплатно
                <ArrowRight className="size-4" />
              </Button>
            </Link>
            <a href="#features">
              <Button size="lg" variant="outline" className="border-border text-foreground hover:bg-secondary">
                Узнать больше
              </Button>
            </a>
          </div>

          {/* Metrics */}
          <div className="mx-auto mt-16 grid max-w-3xl grid-cols-2 gap-8 lg:grid-cols-4">
            {metrics.map((metric) => (
              <div key={metric.label} className="text-center">
                <p className="text-3xl font-bold tracking-tight text-foreground">{metric.value}</p>
                <p className="mt-1 text-sm text-muted-foreground">{metric.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="border-t border-border py-20 lg:py-28">
        <div className="mx-auto max-w-6xl px-4 lg:px-6">
          <div className="text-center">
            <Badge variant="outline" className="mb-4 border-border text-muted-foreground">
              Возможности
            </Badge>
            <h2 className="text-balance text-3xl font-bold tracking-tight lg:text-4xl">
              Всё для мониторинга Telegram
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-pretty text-muted-foreground">
              Мощные инструменты для отслеживания упоминаний, анализа данных и генерации лидов из Telegram-групп.
            </p>
          </div>

          <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <Card key={feature.title} className="border-border bg-card transition-colors hover:bg-card/80">
                <CardContent className="p-6">
                  <div className="flex size-11 items-center justify-center rounded-lg bg-primary/10">
                    <feature.icon className="size-5 text-primary" />
                  </div>
                  <h3 className="mt-4 font-semibold text-card-foreground">{feature.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="border-t border-border py-20 lg:py-28">
        <div className="mx-auto max-w-6xl px-4 lg:px-6">
          <div className="text-center">
            <Badge variant="outline" className="mb-4 border-border text-muted-foreground">
              Тарифы
            </Badge>
            <h2 className="text-balance text-3xl font-bold tracking-tight lg:text-4xl">
              Выберите подходящий план
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-pretty text-muted-foreground">
              Начните бесплатно, масштабируйтесь по мере роста. Все тарифы включают 7-дневный пробный период.
            </p>
          </div>

          <div className="mt-14 grid gap-6 lg:grid-cols-3">
            {plans.map((plan) => (
              <Card
                key={plan.name}
                className={
                  plan.popular
                    ? "relative border-primary bg-card"
                    : "border-border bg-card"
                }
              >
                {plan.popular && (
                  <Badge className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground">
                    Популярный
                  </Badge>
                )}
                <CardContent className="flex flex-col p-6">
                  <h3 className="text-lg font-semibold text-card-foreground">{plan.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{plan.description}</p>

                  <div className="mt-6 flex items-baseline gap-1">
                    <span className="text-4xl font-bold tracking-tight text-card-foreground">{plan.price}</span>
                    <span className="text-sm text-muted-foreground">{" \u20BD"}{plan.period}</span>
                  </div>

                  <ul className="mt-6 flex-1 space-y-3">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-center gap-2.5 text-sm text-secondary-foreground">
                        <Check className="size-4 shrink-0 text-primary" />
                        {feature}
                      </li>
                    ))}
                  </ul>

                  <Link href="/auth?tab=register" className="mt-8 block">
                    <Button
                      className={
                        plan.popular
                          ? "w-full bg-primary text-primary-foreground hover:bg-primary/90"
                          : "w-full bg-secondary text-secondary-foreground hover:bg-secondary/80"
                      }
                    >
                      Начать бесплатно
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section id="testimonials" className="border-t border-border py-20 lg:py-28">
        <div className="mx-auto max-w-6xl px-4 lg:px-6">
          <div className="text-center">
            <Badge variant="outline" className="mb-4 border-border text-muted-foreground">
              Отзывы
            </Badge>
            <h2 className="text-balance text-3xl font-bold tracking-tight lg:text-4xl">
              Нам доверяют 5,000+ пользователей
            </h2>
          </div>

          <div className="mt-14 grid gap-6 lg:grid-cols-3">
            {testimonials.map((t) => (
              <Card key={t.name} className="border-border bg-card">
                <CardContent className="p-6">
                  <div className="flex gap-0.5">
                    {Array.from({ length: t.rating }).map((_, i) => (
                      <Star key={i} className="size-4 fill-warning text-warning" />
                    ))}
                  </div>
                  <p className="mt-4 text-sm leading-relaxed text-secondary-foreground">
                    {'"'}{t.text}{'"'}
                  </p>
                  <div className="mt-5 flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                      {t.initials}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-card-foreground">{t.name}</p>
                      <p className="text-xs text-muted-foreground">{t.role}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="border-t border-border py-20 lg:py-28">
        <div className="mx-auto max-w-3xl px-4 lg:px-6">
          <div className="text-center">
            <Badge variant="outline" className="mb-4 border-border text-muted-foreground">
              FAQ
            </Badge>
            <h2 className="text-balance text-3xl font-bold tracking-tight lg:text-4xl">
              Частые вопросы
            </h2>
          </div>

          <Accordion type="single" collapsible className="mt-10">
            {faqItems.map((item, i) => (
              <AccordionItem key={i} value={`item-${i}`} className="border-border">
                <AccordionTrigger className="text-left text-foreground hover:no-underline">
                  {item.question}
                </AccordionTrigger>
                <AccordionContent className="text-muted-foreground leading-relaxed">
                  {item.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t border-border py-20 lg:py-28">
        <div className="mx-auto max-w-6xl px-4 text-center lg:px-6">
          <div className="mx-auto max-w-2xl">
            <MessageSquare className="mx-auto size-12 text-primary" />
            <h2 className="mt-6 text-balance text-3xl font-bold tracking-tight lg:text-4xl">
              Начните мониторинг Telegram сегодня
            </h2>
            <p className="mt-4 text-pretty text-muted-foreground">
              Присоединяйтесь к тысячам пользователей, которые уже находят лидов и отслеживают упоминания через TeleScope.
            </p>
            <Link href="/auth?tab=register">
              <Button size="lg" className="mt-8 gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
                Создать аккаунт бесплатно
                <ArrowRight className="size-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 sm:flex-row lg:px-6">
          <div className="flex items-center gap-2">
            <div className="flex size-6 items-center justify-center rounded bg-primary">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="text-primary-foreground">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span className="text-sm font-semibold">TeleScope</span>
          </div>
          <p className="text-sm text-muted-foreground">
            {"2024-2026 TeleScope. Все права защищены."}
          </p>
        </div>
      </footer>
    </div>
  )
}
