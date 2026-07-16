import { Injectable } from "@nestjs/common";

@Injectable()
export class ContratosService {
  listarTipos() {
    return [
      {
        codigo: "CPF",
        descricao: "Contrato para pessoa física",
      },
      {
        codigo: "CNPJ",
        descricao: "Contrato para pessoa jurídica",
      },
    ];
  }
}