import { Controller, Get } from "@nestjs/common";
import { ContratosService } from "./contratos.service";

@Controller("contratos")
export class ContratosController {
  constructor(
    private readonly contratosService: ContratosService,
  ) {}

  @Get("tipos")
  listarTipos() {
    return this.contratosService.listarTipos();
  }
}