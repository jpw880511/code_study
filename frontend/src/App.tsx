import type { ReactNode } from 'react'
import AuthProvider from './components/auth/AuthProvider'
import ProtectedRoute from './components/auth/ProtectedRoute'
import ApiTest from './components/dev/ApiTest'
import AuthStoreTest from './components/dev/AuthStoreTest'
import QueryDemo from './components/dev/QueryDemo'
import { ResponsiveGridTest, ShadcnButtonTest, TailwindClassTest } from './components/dev/StyleTest'
import { Button } from './components/ui/button'
import { useAuth } from './hooks/useAuth'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import ProjectDetail from './pages/ProjectDetail'
import Register from './pages/Register'
import TaskDetail from './pages/TaskDetail'
import { BrowserRouter, Link, Outlet, Route, Routes } from 'react-router-dom'

// Placeholder pages: each route below is replaced by its real page in a later task.
function Page({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <section>
      <h1>{title}</h1>
      {children}
    </section>
  )
}

// Every page except login/register shows the navigation bar.
function AppLayout() {
  const { isAuthenticated, logout } = useAuth()
  return (
    <>
      <nav aria-label="주 메뉴">
        <Link to="/">대시보드</Link> <Link to="/trash">휴지통</Link>
        {isAuthenticated && (
          <Button type="button" variant="outline" size="sm" onClick={() => void logout()}>
            로그아웃
          </Button>
        )}
      </nav>
      <main>
        <Outlet />
      </main>
    </>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<AppLayout />}>
        <Route element={<ProtectedRoute />}>
          <Route index element={<Dashboard />} />
          <Route path="/projects/:projectId" element={<ProjectDetail />} />
          <Route path="/tasks/:taskId" element={<TaskDetail />} />
          <Route path="/trash" element={<Page title="휴지통" />} />
          <Route path="*" element={<Page title="페이지를 찾을 수 없습니다" />} />
        </Route>
        {import.meta.env.DEV && (
          <>
            <Route
              path="/dev/query-demo"
              element={
                <Page title="TanStack Query 테스트">
                  <QueryDemo />
                </Page>
              }
            />
            <Route
              path="/dev-test"
              element={
                <Page title="API 테스트">
                  <ApiTest />
                  <h2>Zustand 인증 스토어 테스트</h2>
                  <AuthStoreTest />
                  <h2>Tailwind 클래스 테스트</h2>
                  <TailwindClassTest />
                  <h2>shadcn/ui 버튼 테스트</h2>
                  <ShadcnButtonTest />
                  <h2>반응형 디자인 테스트</h2>
                  <ResponsiveGridTest />
                </Page>
              }
            />
          </>
        )}
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
