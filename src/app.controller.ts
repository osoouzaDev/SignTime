import { Controller, Get } from "@nestjs/common";

@Controller()
export class AppController {
  @Get()
  verificarApi() {
    return {
      nome: "Sistema de Contratos",
      status: "online",
      data: new Date().toISOString(),
    };
  }

  @Get("health")
  verificarSaude() {
    return {
      status: "ok",
    };
  }
}