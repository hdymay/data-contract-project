"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Upload, FileText, CheckCircle, AlertTriangle, Info, Scale } from "lucide-react"

interface ValidationError {
  type: "error" | "warning" | "info"
  title: string
  description: string
  line?: number
  suggestion?: string
}

interface ContractValidationAgentProps {
  onFileUpload?: (file: File) => void
  onAnalysisStart?: (file: File) => void
  validationErrors?: ValidationError[]
  isAnalyzing?: boolean
  analysisProgress?: number
  analysisComplete?: boolean
}

export default function ContractValidationAgent({
  onFileUpload,
  onAnalysisStart,
  validationErrors = [],
  isAnalyzing = false,
  analysisProgress = 0,
  analysisComplete = false,
}: ContractValidationAgentProps) {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [localAnalyzing, setLocalAnalyzing] = useState(false)
  const [localProgress, setLocalProgress] = useState(0)
  const [localComplete, setLocalComplete] = useState(false)

  const currentAnalyzing = isAnalyzing || localAnalyzing
  const currentProgress = analysisProgress || localProgress
  const currentComplete = analysisComplete || localComplete

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setUploadedFile(file)
      setLocalComplete(false)
      onFileUpload?.(file)
    }
  }

  const startAnalysis = () => {
    if (!uploadedFile) return

    if (onAnalysisStart) {
      onAnalysisStart(uploadedFile)
    } else {
      setLocalAnalyzing(true)
      setLocalProgress(0)

      const interval = setInterval(() => {
        setLocalProgress((prev) => {
          if (prev >= 100) {
            clearInterval(interval)
            setLocalAnalyzing(false)
            setLocalComplete(true)
            return 100
          }
          return prev + 10
        })
      }, 300)
    }
  }

  const mockValidationResults = {
    overallScore: 85,
    issues:
      validationErrors.length > 0
        ? validationErrors
        : [
            {
              type: "warning" as const,
              title: "계약 기간 명시 부족",
              description: "계약 기간이 명확하게 명시되지 않았습니다.",
            },
            {
              type: "error" as const,
              title: "손해배상 조항 누락",
              description: "표준계약서에 포함된 손해배상 조항이 누락되었습니다.",
            },
            {
              type: "info" as const,
              title: "권리 의무 조항 확인",
              description: "당사자 간 권리와 의무가 적절히 명시되어 있습니다.",
            },
          ],
    standardComparison: {
      matched: 12,
      missing: 3,
      additional: 2,
    },
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-12 h-12 bg-primary rounded-lg">
              <Scale className="w-6 h-6 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">계약서 검증 에이전트</h1>
              <p className="text-muted-foreground">AI 기반 계약서 분석 및 표준계약서 비교 도구</p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 업로드 섹션 */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="w-5 h-5" />
                  계약서 업로드
                </CardTitle>
                <CardDescription>
                  검증하고자 하는 계약서를 업로드해주세요. PDF, DOC, DOCX 파일을 지원합니다.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="border-2 border-dashed border-border rounded-lg p-8 text-center">
                  <input
                    type="file"
                    accept=".pdf,.doc,.docx"
                    onChange={handleFileUpload}
                    className="hidden"
                    id="file-upload"
                  />
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <div className="flex flex-col items-center gap-4">
                      <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center">
                        <FileText className="w-8 h-8 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-lg font-medium">파일을 선택하거나 드래그하여 업로드</p>
                        <p className="text-sm text-muted-foreground mt-1">최대 10MB, PDF/DOC/DOCX 형식 지원</p>
                      </div>
                    </div>
                  </label>
                </div>

                {uploadedFile && (
                  <div className="mt-4 p-4 bg-muted rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-primary" />
                        <div>
                          <p className="font-medium">{uploadedFile.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {(uploadedFile.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </div>
                      </div>
                      <Button
                        onClick={startAnalysis}
                        disabled={currentAnalyzing}
                        className="bg-primary hover:bg-primary/90"
                      >
                        {currentAnalyzing ? "분석 중..." : "검증 시작"}
                      </Button>
                    </div>
                  </div>
                )}

                {currentAnalyzing && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">분석 진행률</span>
                      <span className="text-sm text-muted-foreground">{currentProgress}%</span>
                    </div>
                    <Progress value={currentProgress} className="w-full" />
                  </div>
                )}

                {validationErrors.length > 0 && !currentAnalyzing && (
                  <div className="mt-4 space-y-3">
                    <h3 className="text-lg font-semibold text-red-600 flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5" />
                      업로드 오류 발견
                    </h3>
                    {validationErrors.map((error, index) => (
                      <Alert
                        key={index}
                        className={
                          error.type === "error"
                            ? "border-red-200 bg-red-50"
                            : error.type === "warning"
                              ? "border-orange-200 bg-orange-50"
                              : "border-blue-200 bg-blue-50"
                        }
                      >
                        <div className="flex items-start gap-3">
                          {error.type === "error" && <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5" />}
                          {error.type === "warning" && <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5" />}
                          {error.type === "info" && <Info className="w-5 h-5 text-blue-600 mt-0.5" />}
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <h4 className="font-medium">{error.title}</h4>
                              <Badge
                                variant={
                                  error.type === "error"
                                    ? "destructive"
                                    : error.type === "warning"
                                      ? "secondary"
                                      : "default"
                                }
                              >
                                {error.type === "error" ? "오류" : error.type === "warning" ? "경고" : "정보"}
                              </Badge>
                              {error.line && (
                                <Badge variant="outline" className="text-xs">
                                  {error.line}행
                                </Badge>
                              )}
                            </div>
                            <AlertDescription className="mb-2">{error.description}</AlertDescription>
                            {error.suggestion && (
                              <div className="mt-2 p-2 bg-background rounded border-l-4 border-primary">
                                <p className="text-sm font-medium text-primary">권장 수정사항:</p>
                                <p className="text-sm text-muted-foreground">{error.suggestion}</p>
                              </div>
                            )}
                          </div>
                        </div>
                      </Alert>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 분석 결과 */}
            {currentComplete && (
              <Card className="mt-6">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    검증 결과
                  </CardTitle>
                  <CardDescription>표준계약서와의 비교 분석 결과입니다.</CardDescription>
                </CardHeader>
                <CardContent>
                  <Tabs defaultValue="overview" className="w-full">
                    <TabsList className="grid w-full grid-cols-3">
                      <TabsTrigger value="overview">종합 분석</TabsTrigger>
                      <TabsTrigger value="issues">발견된 이슈</TabsTrigger>
                      <TabsTrigger value="comparison">표준계약서 비교</TabsTrigger>
                    </TabsList>

                    <TabsContent value="overview" className="space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Card>
                          <CardContent className="p-4 text-center">
                            <div className="text-3xl font-bold text-primary mb-1">
                              {mockValidationResults.overallScore}
                            </div>
                            <p className="text-sm text-muted-foreground">종합 점수</p>
                          </CardContent>
                        </Card>
                        <Card>
                          <CardContent className="p-4 text-center">
                            <div className="text-3xl font-bold text-green-600 mb-1">
                              {mockValidationResults.standardComparison.matched}
                            </div>
                            <p className="text-sm text-muted-foreground">일치 조항</p>
                          </CardContent>
                        </Card>
                        <Card>
                          <CardContent className="p-4 text-center">
                            <div className="text-3xl font-bold text-orange-600 mb-1">
                              {mockValidationResults.standardComparison.missing}
                            </div>
                            <p className="text-sm text-muted-foreground">누락 조항</p>
                          </CardContent>
                        </Card>
                      </div>
                    </TabsContent>

                    <TabsContent value="issues" className="space-y-4">
                      {mockValidationResults.issues.map((issue, index) => (
                        <Alert
                          key={index}
                          className={
                            issue.type === "error"
                              ? "border-red-200 bg-red-50"
                              : issue.type === "warning"
                                ? "border-orange-200 bg-orange-50"
                                : "border-blue-200 bg-blue-50"
                          }
                        >
                          <div className="flex items-start gap-3">
                            {issue.type === "error" && <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5" />}
                            {issue.type === "warning" && <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5" />}
                            {issue.type === "info" && <Info className="w-5 h-5 text-blue-600 mt-0.5" />}
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <h4 className="font-medium">{issue.title}</h4>
                                <Badge
                                  variant={
                                    issue.type === "error"
                                      ? "destructive"
                                      : issue.type === "warning"
                                        ? "secondary"
                                        : "default"
                                  }
                                >
                                  {issue.type === "error" ? "오류" : issue.type === "warning" ? "경고" : "정보"}
                                </Badge>
                              </div>
                              <AlertDescription>{issue.description}</AlertDescription>
                            </div>
                          </div>
                        </Alert>
                      ))}
                    </TabsContent>

                    <TabsContent value="comparison" className="space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <Card>
                          <CardHeader>
                            <CardTitle className="text-lg">표준계약서 조항</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-2">
                              <div className="flex items-center justify-between p-2 bg-green-50 rounded">
                                <span className="text-sm">계약 당사자 명시</span>
                                <CheckCircle className="w-4 h-4 text-green-600" />
                              </div>
                              <div className="flex items-center justify-between p-2 bg-green-50 rounded">
                                <span className="text-sm">계약 목적 및 범위</span>
                                <CheckCircle className="w-4 h-4 text-green-600" />
                              </div>
                              <div className="flex items-center justify-between p-2 bg-red-50 rounded">
                                <span className="text-sm">손해배상 조항</span>
                                <AlertTriangle className="w-4 h-4 text-red-600" />
                              </div>
                            </div>
                          </CardContent>
                        </Card>

                        <Card>
                          <CardHeader>
                            <CardTitle className="text-lg">권장 개선사항</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-3">
                              <div className="p-3 bg-blue-50 rounded-lg">
                                <h5 className="font-medium text-sm mb-1">계약기간 명시 권장</h5>
                                <p className="text-xs text-muted-foreground">
                                  명확한 계약기간을 명시하여 분쟁을 예방하세요.
                                </p>
                              </div>
                              <div className="p-3 bg-blue-50 rounded-lg">
                                <h5 className="font-medium text-sm mb-1">해지 조건 상세화</h5>
                                <p className="text-xs text-muted-foreground">
                                  계약 해지 조건을 구체적으로 명시하는 것이 좋습니다.
                                </p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      </div>
                    </TabsContent>
                  </Tabs>
                </CardContent>
              </Card>
            )}
          </div>

          {/* 사이드바 */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">표준계약서 라이브러리</CardTitle>
                <CardDescription>관리자가 업로드한 표준계약서 목록입니다. (관리자 전용 업로드)</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="p-3 border rounded-lg">
                    <h4 className="font-medium text-sm">용역계약서</h4>
                    <p className="text-xs text-muted-foreground mt-1">일반적인 용역 제공 계약</p>
                  </div>
                  <div className="p-3 border rounded-lg">
                    <h4 className="font-medium text-sm">매매계약서</h4>
                    <p className="text-xs text-muted-foreground mt-1">물품 매매 관련 계약</p>
                  </div>
                  <div className="p-3 border rounded-lg">
                    <h4 className="font-medium text-sm">임대차계약서</h4>
                    <p className="text-xs text-muted-foreground mt-1">부동산 임대차 계약</p>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t">
                  <Button variant="outline" size="sm" className="w-full bg-transparent" disabled>
                    <Upload className="w-4 h-4 mr-2" />
                    표준계약서 업로드 (관리자 전용)
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}
