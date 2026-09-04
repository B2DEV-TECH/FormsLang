-- ============================================================================
-- Schema de apoio para tests/fixtures/showcase/module.xml (DEMO_ALL_ELEMENTS)
--
-- Cria tudo que o form espera encontrar no schema FORMSLANG -- mesmo schema do
-- apex_username em config.json -- pra compilar e rodar de verdade no Forms
-- Builder. 100% sintetico, sem dado de cliente.
--
-- Objetos (na ordem de criacao):
--   TAB_CATEGORIA        -> RG_CATEGORIA / LOV_CATEGORIA (FK_CATEGORIA)
--   TAB_FORNECEDOR       -> RG_FORNECEDOR / LOV_FORNECEDOR (FK_FORNECEDOR)
--   TAB_PRODUTO          -> bloco mestre BK_PRODUTO
--   TAB_PRODUTO_SEQ      -> PRE-INSERT de BK_PRODUTO
--   TAB_PRODUTO_ITEM     -> bloco detalhe BK_ITENS (REL_ITENS)
--   TAB_PRODUTO_AUDIT    -> bloco detalhe somente-leitura BK_AUDIT (REL_AUDIT),
--                           alimentado pelo trigger de banco TRG_TAB_PRODUTO_AUDIT
--   TAB_FORM_ACESSO      -> INSERT feito pelo PRE-FORM do form (log de acesso)
--   VW_PRODUTO_RESUMO    -> bloco somente-leitura BK_RESUMO (agregado por categoria)
--   PKG_PRODUTO          -> regras que JA moram no banco e o form so chama:
--                           F_VALIDA_EAN13, F_TOTAL_ITENS, F_DS_STATUS,
--                           P_APLICA_REAJUSTE
--
-- Como rodar: conectado como SYSTEM (ou qualquer usuario com privilegio de
-- trocar de schema) no FREEPDB1, execute o script inteiro de uma vez no
-- PL/SQL Developer. Se preferir, conecte direto como FORMSLANG e apague a
-- linha ALTER SESSION abaixo. Por SQLcl:
--   sql -S -thin FORMSLANG/<senha>@localhost:1521/FREEPDB1 @demo_schema.sql
-- ============================================================================

ALTER SESSION SET CURRENT_SCHEMA = FORMSLANG;

-- Reset idempotente (ignora "objeto nao existe" -- ORA-00942 tabela/view,
-- ORA-02289 sequence, ORA-04043 package) pra poder rodar o script de novo.
BEGIN
   EXECUTE IMMEDIATE 'DROP VIEW VW_PRODUTO_RESUMO';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN
   EXECUTE IMMEDIATE 'DROP PACKAGE PKG_PRODUTO';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -4043 THEN RAISE; END IF; END;
/
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE TAB_PRODUTO_AUDIT';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE TAB_FORM_ACESSO';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE TAB_PRODUTO_ITEM';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE TAB_PRODUTO';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE TAB_FORNECEDOR';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE TAB_CATEGORIA';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN
   EXECUTE IMMEDIATE 'DROP SEQUENCE TAB_PRODUTO_SEQ';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -2289 THEN RAISE; END IF; END;
/

-- ----------------------------------------------------------------------------
-- TAB_CATEGORIA -- alimenta RG_CATEGORIA (Record Group de Query) usado por
-- DUAS LOVs (LOV_CATEGORIA em BK_PRODUTO.FK_CATEGORIA e LOV_CATEGORIA_REAJUSTE
-- em CONTROL.PC_CATEGORIA). Precisa ter linhas antes de abrir o form.
-- ----------------------------------------------------------------------------
CREATE TABLE TAB_CATEGORIA (
   ID_CATEGORIA   NUMBER        NOT NULL,
   DS_CATEGORIA   VARCHAR2(60)  NOT NULL,
   CONSTRAINT PK_TAB_CATEGORIA PRIMARY KEY (ID_CATEGORIA)
);

INSERT INTO TAB_CATEGORIA (ID_CATEGORIA, DS_CATEGORIA) VALUES (1, 'Eletronicos');
INSERT INTO TAB_CATEGORIA (ID_CATEGORIA, DS_CATEGORIA) VALUES (2, 'Alimentos');
INSERT INTO TAB_CATEGORIA (ID_CATEGORIA, DS_CATEGORIA) VALUES (3, 'Vestuario');
INSERT INTO TAB_CATEGORIA (ID_CATEGORIA, DS_CATEGORIA) VALUES (4, 'Ferramentas');

-- ----------------------------------------------------------------------------
-- TAB_FORNECEDOR -- alimenta RG_FORNECEDOR / LOV_FORNECEDOR (aba Comercial).
-- A LOV filtra FL_HOMOLOGADO = 'Y', entao o 4o fornecedor NAO aparece nela
-- de proposito (demonstra WHERE no Record Group).
-- ----------------------------------------------------------------------------
CREATE TABLE TAB_FORNECEDOR (
   ID_FORNECEDOR   NUMBER        NOT NULL,
   NM_FORNECEDOR   VARCHAR2(80)  NOT NULL,
   CD_CNPJ         VARCHAR2(18),
   FL_HOMOLOGADO   CHAR(1)       DEFAULT 'Y' NOT NULL,
   CONSTRAINT PK_TAB_FORNECEDOR PRIMARY KEY (ID_FORNECEDOR),
   CONSTRAINT CK_TAB_FORNECEDOR_HOMOLOG CHECK (FL_HOMOLOGADO IN ('Y', 'N'))
);

INSERT INTO TAB_FORNECEDOR VALUES (1, 'Ferramentas Alfa Ltda',        '12.345.678/0001-90', 'Y');
INSERT INTO TAB_FORNECEDOR VALUES (2, 'Eletro Beta Importadora S.A.', '23.456.789/0001-01', 'Y');
INSERT INTO TAB_FORNECEDOR VALUES (3, 'Alimentos Gama Distribuidora', '34.567.890/0001-12', 'Y');
INSERT INTO TAB_FORNECEDOR VALUES (4, 'Textil Delta (nao homologado)', '45.678.901/0001-23', 'N');

-- ----------------------------------------------------------------------------
-- TAB_PRODUTO -- bloco mestre BK_PRODUTO. Colunas na mesma ordem/nome dos
-- Item/ColumnName do module.xml. As quatro ultimas (FK_FORNECEDOR,
-- DT_CADASTRO, DT_ALTERACAO, NM_USUARIO_ALT) moram na aba Comercial e sao
-- preenchidas pelos triggers PRE-INSERT/PRE-UPDATE do bloco.
-- ----------------------------------------------------------------------------
CREATE TABLE TAB_PRODUTO (
   PK_ID           NUMBER(10)     NOT NULL,
   DS_NOME         VARCHAR2(100)  NOT NULL,
   DS_DESCRICAO    VARCHAR2(200),
   DS_OBS_LONGA    VARCHAR2(500),
   VL_PRECO        NUMBER(12,2)   NOT NULL,
   DT_VALIDADE     DATE,
   FK_CATEGORIA    NUMBER,
   TP_UNIDADE      VARCHAR2(10),
   TP_STATUS       VARCHAR2(15)   NOT NULL,
   FL_ATIVO        CHAR(1)        DEFAULT 'Y' NOT NULL,
   ID_INTERNO      NUMBER,
   OBS_INTERNA     VARCHAR2(200),
   NR_SEQ          NUMBER,
   CD_LOTE         VARCHAR2(15),
   CD_BARRA        VARCHAR2(20),
   NR_PALETE       NUMBER,
   NR_CAIXA        NUMBER,
   NR_UNIDADE      NUMBER,
   VL_PESO_BRUTO   NUMBER(10,3),
   VL_PESO_LIQ     NUMBER(10,3),
   PESO_KG         NUMBER(10,3),
   QTDE_EST        NUMBER,
   OBS_GERAL       VARCHAR2(4000),
   FK_FORNECEDOR   NUMBER,
   DT_CADASTRO     DATE,
   DT_ALTERACAO    DATE,
   NM_USUARIO_ALT  VARCHAR2(30),
   CONSTRAINT PK_TAB_PRODUTO PRIMARY KEY (PK_ID),
   CONSTRAINT FK_TAB_PRODUTO_CATEGORIA FOREIGN KEY (FK_CATEGORIA)
      REFERENCES TAB_CATEGORIA (ID_CATEGORIA),
   CONSTRAINT FK_TAB_PRODUTO_FORNECEDOR FOREIGN KEY (FK_FORNECEDOR)
      REFERENCES TAB_FORNECEDOR (ID_FORNECEDOR),
   CONSTRAINT CK_TAB_PRODUTO_FL_ATIVO CHECK (FL_ATIVO IN ('Y', 'N')),
   CONSTRAINT CK_TAB_PRODUTO_TP_STATUS CHECK (TP_STATUS IN ('ATIVO', 'INATIVO', 'BLOQUEADO'))
);

-- O trigger PRE-INSERT do bloco (":PK_ID := TAB_PRODUTO_SEQ.NEXTVAL;") espera
-- esta sequence com exatamente este nome.
CREATE SEQUENCE TAB_PRODUTO_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;

-- ----------------------------------------------------------------------------
-- TAB_PRODUTO_ITEM -- bloco detalhe BK_ITENS (master-detail via REL_ITENS,
-- join BK_PRODUTO.PK_ID = BK_ITENS.FK_PRODUTO_ID). SEQ_ITEM e gerado pelo
-- PRE-INSERT de BK_ITENS (MAX+1 dentro do produto).
-- ----------------------------------------------------------------------------
CREATE TABLE TAB_PRODUTO_ITEM (
   FK_PRODUTO_ID   NUMBER(10)     NOT NULL,
   SEQ_ITEM        NUMBER         NOT NULL,
   DS_ITEM         VARCHAR2(120)  NOT NULL,
   QT_ITEM         NUMBER         NOT NULL,
   VL_UNIT         NUMBER(12,2)   NOT NULL,
   CONSTRAINT PK_TAB_PRODUTO_ITEM PRIMARY KEY (FK_PRODUTO_ID, SEQ_ITEM),
   CONSTRAINT FK_TAB_PRODUTO_ITEM_PRODUTO FOREIGN KEY (FK_PRODUTO_ID)
      REFERENCES TAB_PRODUTO (PK_ID)
);

-- ----------------------------------------------------------------------------
-- TAB_PRODUTO_AUDIT -- trilha de auditoria de TAB_PRODUTO, escrita SO pelo
-- trigger de banco abaixo (o form nunca insere aqui: BK_AUDIT e
-- Insert/Update/Delete Allowed = false). Sem FK pro produto de proposito:
-- a linha de DELETE precisa sobreviver ao produto.
-- ----------------------------------------------------------------------------
CREATE TABLE TAB_PRODUTO_AUDIT (
   ID_AUDIT        NUMBER GENERATED ALWAYS AS IDENTITY,
   FK_PRODUTO_ID   NUMBER(10)     NOT NULL,
   TP_OPERACAO     VARCHAR2(10)   NOT NULL,
   DT_OPERACAO     DATE           NOT NULL,
   NM_USUARIO      VARCHAR2(30)   NOT NULL,
   VL_PRECO_ANT    NUMBER(12,2),
   VL_PRECO_NOVO   NUMBER(12,2),
   DS_DETALHE      VARCHAR2(400),
   CONSTRAINT PK_TAB_PRODUTO_AUDIT PRIMARY KEY (ID_AUDIT),
   CONSTRAINT CK_TAB_PRODUTO_AUDIT_OP CHECK (TP_OPERACAO IN ('INSERT', 'UPDATE', 'DELETE'))
);

CREATE INDEX IX_TAB_PRODUTO_AUDIT_PROD ON TAB_PRODUTO_AUDIT (FK_PRODUTO_ID, DT_OPERACAO);

-- ----------------------------------------------------------------------------
-- TAB_FORM_ACESSO -- log de abertura do form. O PRE-FORM faz o INSERT
-- diretamente (SQL embutido no form + FORMS_DDL('COMMIT'), padrao legado
-- classico que o assess do FormsLang precisa enxergar).
-- ----------------------------------------------------------------------------
CREATE TABLE TAB_FORM_ACESSO (
   ID_ACESSO       NUMBER GENERATED ALWAYS AS IDENTITY,
   NM_FORM         VARCHAR2(60)   NOT NULL,
   NM_USUARIO      VARCHAR2(30)   NOT NULL,
   DT_ACESSO       DATE           NOT NULL,
   CONSTRAINT PK_TAB_FORM_ACESSO PRIMARY KEY (ID_ACESSO)
);

-- ----------------------------------------------------------------------------
-- VW_PRODUTO_RESUMO -- fonte do bloco somente-leitura BK_RESUMO (aba Resumo).
-- View agregada nao tem ROWID: o bloco usa KeyMode="Non-Updateable" com
-- ID_CATEGORIA marcado PrimaryKey, senao o Forms tenta selecionar ROWID e
-- falha na consulta.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW VW_PRODUTO_RESUMO AS
SELECT c.ID_CATEGORIA,
       c.DS_CATEGORIA,
       COUNT(p.PK_ID)                                            AS QT_PRODUTOS,
       SUM(CASE WHEN p.TP_STATUS = 'ATIVO'     THEN 1 ELSE 0 END) AS QT_ATIVOS,
       SUM(CASE WHEN p.TP_STATUS = 'BLOQUEADO' THEN 1 ELSE 0 END) AS QT_BLOQUEADOS,
       ROUND(AVG(p.VL_PRECO), 2)                                 AS VL_PRECO_MEDIO,
       NVL(SUM(p.QTDE_EST * p.VL_PRECO), 0)                      AS VL_ESTOQUE
  FROM TAB_CATEGORIA c
  LEFT JOIN TAB_PRODUTO p ON p.FK_CATEGORIA = c.ID_CATEGORIA
 GROUP BY c.ID_CATEGORIA, c.DS_CATEGORIA;

-- ----------------------------------------------------------------------------
-- PKG_PRODUTO -- regra de negocio que JA mora no banco. O form so chama
-- (WHEN-VALIDATE-ITEM de CD_BARRA, P_CALC_TOTAL_ITENS, BT_APLICAR do
-- reajuste). Na migracao pra APEX este codigo nao muda -- e exatamente o
-- contraste que o assess do FormsLang quer mostrar: logica de servidor
-- fica, logica de cliente (triggers do form) e que vira trabalho.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PACKAGE PKG_PRODUTO AS

   -- Valida digito verificador EAN-13. Retorna 'S'/'N' (nao BOOLEAN) porque o
   -- PL/SQL do Forms conversa com o banco por RPC e VARCHAR2 e o contrato
   -- mais portavel.
   FUNCTION F_VALIDA_EAN13 (p_codigo IN VARCHAR2) RETURN VARCHAR2;

   -- Soma QT_ITEM * VL_UNIT dos itens de um produto (0 se nao houver).
   FUNCTION F_TOTAL_ITENS (p_produto_id IN NUMBER) RETURN NUMBER;

   -- Rotulo legivel do status (ATIVO -> 'Ativo' etc).
   FUNCTION F_DS_STATUS (p_tp_status IN VARCHAR2) RETURN VARCHAR2;

   -- Reajusta VL_PRECO de todos os produtos ativos de uma categoria.
   -- Nao faz COMMIT: quem chama decide (o form usa FORMS_DDL('COMMIT')).
   PROCEDURE P_APLICA_REAJUSTE (p_categoria      IN  NUMBER,
                                p_percentual     IN  NUMBER,
                                p_usuario        IN  VARCHAR2,
                                p_qtd_atualizada OUT NUMBER);

END PKG_PRODUTO;
/

CREATE OR REPLACE PACKAGE BODY PKG_PRODUTO AS

   FUNCTION F_VALIDA_EAN13 (p_codigo IN VARCHAR2) RETURN VARCHAR2 IS
      v_soma   PLS_INTEGER := 0;
      v_digito PLS_INTEGER;
   BEGIN
      IF p_codigo IS NULL OR NOT REGEXP_LIKE(p_codigo, '^[0-9]{13}$') THEN
         RETURN 'N';
      END IF;
      -- Posicoes impares pesam 1, pares pesam 3 (contando da esquerda).
      FOR i IN 1 .. 12 LOOP
         v_soma := v_soma + TO_NUMBER(SUBSTR(p_codigo, i, 1))
                          * CASE WHEN MOD(i, 2) = 1 THEN 1 ELSE 3 END;
      END LOOP;
      v_digito := MOD(10 - MOD(v_soma, 10), 10);
      IF v_digito = TO_NUMBER(SUBSTR(p_codigo, 13, 1)) THEN
         RETURN 'S';
      END IF;
      RETURN 'N';
   END F_VALIDA_EAN13;

   FUNCTION F_TOTAL_ITENS (p_produto_id IN NUMBER) RETURN NUMBER IS
      v_total NUMBER;
   BEGIN
      SELECT NVL(SUM(QT_ITEM * VL_UNIT), 0)
        INTO v_total
        FROM TAB_PRODUTO_ITEM
       WHERE FK_PRODUTO_ID = p_produto_id;
      RETURN v_total;
   END F_TOTAL_ITENS;

   FUNCTION F_DS_STATUS (p_tp_status IN VARCHAR2) RETURN VARCHAR2 IS
   BEGIN
      RETURN CASE p_tp_status
                WHEN 'ATIVO'     THEN 'Ativo'
                WHEN 'INATIVO'   THEN 'Inativo'
                WHEN 'BLOQUEADO' THEN 'Bloqueado (aguardando laudo)'
                ELSE p_tp_status
             END;
   END F_DS_STATUS;

   PROCEDURE P_APLICA_REAJUSTE (p_categoria      IN  NUMBER,
                                p_percentual     IN  NUMBER,
                                p_usuario        IN  VARCHAR2,
                                p_qtd_atualizada OUT NUMBER) IS
   BEGIN
      IF p_percentual IS NULL OR p_percentual <= -100 THEN
         RAISE_APPLICATION_ERROR(-20001, 'Percentual de reajuste invalido: ' || p_percentual);
      END IF;
      UPDATE TAB_PRODUTO
         SET VL_PRECO       = ROUND(VL_PRECO * (1 + p_percentual / 100), 2),
             DT_ALTERACAO   = SYSDATE,
             NM_USUARIO_ALT = NVL(p_usuario, USER)
       WHERE FK_CATEGORIA = p_categoria
         AND FL_ATIVO     = 'Y';
      p_qtd_atualizada := SQL%ROWCOUNT;
   END P_APLICA_REAJUSTE;

END PKG_PRODUTO;
/

-- ----------------------------------------------------------------------------
-- TRG_TAB_PRODUTO_AUDIT -- toda mudanca em TAB_PRODUTO vira linha em
-- TAB_PRODUTO_AUDIT, venha do form, do PKG_PRODUTO.P_APLICA_REAJUSTE ou de
-- um UPDATE solto. NM_USUARIO usa o que o form gravou em NM_USUARIO_ALT
-- (:GLOBAL.USUARIO) e cai pro USER do banco quando nao houver.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE TRIGGER TRG_TAB_PRODUTO_AUDIT
   AFTER INSERT OR UPDATE OR DELETE ON TAB_PRODUTO
   FOR EACH ROW
DECLARE
   v_op      VARCHAR2(10);
   v_detalhe VARCHAR2(400);
BEGIN
   IF INSERTING THEN
      v_op      := 'INSERT';
      v_detalhe := 'Produto cadastrado: ' || :NEW.DS_NOME;
   ELSIF UPDATING THEN
      v_op := 'UPDATE';
      IF NVL(:OLD.VL_PRECO, -1) != NVL(:NEW.VL_PRECO, -1) THEN
         v_detalhe := 'Preco alterado de ' || TO_CHAR(:OLD.VL_PRECO, 'FM999G999G990D00')
                   || ' para ' || TO_CHAR(:NEW.VL_PRECO, 'FM999G999G990D00');
      ELSIF NVL(:OLD.TP_STATUS, '-') != NVL(:NEW.TP_STATUS, '-') THEN
         v_detalhe := 'Status alterado de ' || :OLD.TP_STATUS || ' para ' || :NEW.TP_STATUS;
      ELSE
         v_detalhe := 'Dados alterados: ' || :NEW.DS_NOME;
      END IF;
   ELSE
      v_op      := 'DELETE';
      v_detalhe := 'Produto excluido: ' || :OLD.DS_NOME;
   END IF;

   INSERT INTO TAB_PRODUTO_AUDIT
      (FK_PRODUTO_ID, TP_OPERACAO, DT_OPERACAO, NM_USUARIO,
       VL_PRECO_ANT, VL_PRECO_NOVO, DS_DETALHE)
   VALUES
      (NVL(:NEW.PK_ID, :OLD.PK_ID), v_op, SYSDATE,
       COALESCE(:NEW.NM_USUARIO_ALT, :OLD.NM_USUARIO_ALT, USER),
       :OLD.VL_PRECO, :NEW.VL_PRECO, v_detalhe);
END;
/

COMMIT;

-- ============================================================================
-- Seed -- 6 produtos cobrindo as 4 categorias, os 3 fornecedores homologados
-- e os 3 valores de TP_STATUS (RB_ATIVO/RB_INATIVO/RB_BLOQUEADO no Radio
-- Group), com as colunas "esteticas" preenchidas pra abrir o form ja com
-- tela de dados de verdade. Os codigos de barra sao EAN-13 validos (digito
-- verificador correto), senao o WHEN-VALIDATE-ITEM de CD_BARRA barra a
-- edicao do registro.
--
-- Dois produtos (Camiseta e Parafusadeira) ficam de proposito sem item de
-- detalhe, pra demonstrar que o totalizador (VL_TOTAL_ITENS via
-- PKG_PRODUTO.F_TOTAL_ITENS) mostra 0 corretamente em vez de branco ou erro.
--
-- Notebook e Parafusadeira nascem ATIVO e sao alterados logo abaixo
-- (INATIVO / BLOQUEADO) pra aba Auditoria abrir com historico de UPDATE
-- gerado pelo trigger de banco, alem dos INSERTs.
-- ============================================================================
INSERT INTO TAB_PRODUTO (PK_ID, DS_NOME, DS_DESCRICAO, DS_OBS_LONGA, VL_PRECO,
                          DT_VALIDADE, FK_CATEGORIA, TP_UNIDADE, TP_STATUS,
                          FL_ATIVO, ID_INTERNO, OBS_INTERNA, NR_SEQ, CD_LOTE,
                          CD_BARRA, NR_PALETE, NR_CAIXA, NR_UNIDADE,
                          VL_PESO_BRUTO, VL_PESO_LIQ, PESO_KG, QTDE_EST,
                          OBS_GERAL, FK_FORNECEDOR, DT_CADASTRO, DT_ALTERACAO, NM_USUARIO_ALT)
VALUES (TAB_PRODUTO_SEQ.NEXTVAL, 'Furadeira de Impacto 750W',
        'Furadeira/parafusadeira de impacto, maleta plastica',
        'Motor 750W, mandril 13mm, 2 velocidades, maleta plastica com kit de brocas incluso.',
        349.90, DATE '2028-12-31', 4, 'UNIDADE', 'ATIVO', 'Y',
        100234, 'Fornecedor homologado, reposicao trimestral', 10, 'L2026-089',
        '7896543210012', 5, 12, 1, 2.850, 2.600, 2.600, 40,
        'Produto carro-chefe da linha Ferramentas, alta rotatividade.',
        1, DATE '2026-01-15', DATE '2026-01-15', 'SEED');

INSERT INTO TAB_PRODUTO (PK_ID, DS_NOME, DS_DESCRICAO, DS_OBS_LONGA, VL_PRECO,
                          DT_VALIDADE, FK_CATEGORIA, TP_UNIDADE, TP_STATUS,
                          FL_ATIVO, ID_INTERNO, OBS_INTERNA, NR_SEQ, CD_LOTE,
                          CD_BARRA, NR_PALETE, NR_CAIXA, NR_UNIDADE,
                          VL_PESO_BRUTO, VL_PESO_LIQ, PESO_KG, QTDE_EST,
                          OBS_GERAL, FK_FORNECEDOR, DT_CADASTRO, DT_ALTERACAO, NM_USUARIO_ALT)
VALUES (TAB_PRODUTO_SEQ.NEXTVAL, 'Fone Bluetooth ANC',
        'Fone over-ear com cancelamento de ruido ativo',
        'Bluetooth 5.3, ANC ate 35dB, bateria 30h, estojo rigido incluso.',
        459.00, DATE '2028-06-30', 1, 'CAIXA', 'ATIVO', 'Y',
        100511, 'Garantia estendida do fabricante, 24 meses', 20, 'L2026-142',
        '7896543210029', 3, 24, 1, 0.420, 0.310, 0.310, 120,
        'Segunda geracao, substitui o modelo anterior descontinuado.',
        2, DATE '2026-02-03', DATE '2026-02-03', 'SEED');

INSERT INTO TAB_PRODUTO (PK_ID, DS_NOME, DS_DESCRICAO, DS_OBS_LONGA, VL_PRECO,
                          DT_VALIDADE, FK_CATEGORIA, TP_UNIDADE, TP_STATUS,
                          FL_ATIVO, ID_INTERNO, OBS_INTERNA, NR_SEQ, CD_LOTE,
                          CD_BARRA, NR_PALETE, NR_CAIXA, NR_UNIDADE,
                          VL_PESO_BRUTO, VL_PESO_LIQ, PESO_KG, QTDE_EST,
                          OBS_GERAL, FK_FORNECEDOR, DT_CADASTRO, DT_ALTERACAO, NM_USUARIO_ALT)
VALUES (TAB_PRODUTO_SEQ.NEXTVAL, 'Cafe Especial Grao 1kg',
        'Cafe arabica torra media, graos inteiros, pacote 1kg',
        'Origem unica, torra media, notas de caramelo e castanha. Validade curta, controlar giro de estoque.',
        58.90, DATE '2026-12-15', 2, 'UNIDADE', 'ATIVO', 'Y',
        100788, 'Perecivel, FEFO obrigatorio', 30, 'L2026-201',
        '7896543210036', 8, 20, 1, 1.050, 1.000, 1.000, 200,
        'Alta demanda sazonal, reforcar estoque no fim de ano.',
        3, DATE '2026-03-10', DATE '2026-03-10', 'SEED');

INSERT INTO TAB_PRODUTO (PK_ID, DS_NOME, DS_DESCRICAO, DS_OBS_LONGA, VL_PRECO,
                          DT_VALIDADE, FK_CATEGORIA, TP_UNIDADE, TP_STATUS,
                          FL_ATIVO, ID_INTERNO, OBS_INTERNA, NR_SEQ, CD_LOTE,
                          CD_BARRA, NR_PALETE, NR_CAIXA, NR_UNIDADE,
                          VL_PESO_BRUTO, VL_PESO_LIQ, PESO_KG, QTDE_EST,
                          OBS_GERAL, FK_FORNECEDOR, DT_CADASTRO, DT_ALTERACAO, NM_USUARIO_ALT)
VALUES (TAB_PRODUTO_SEQ.NEXTVAL, 'Camiseta Basica Algodao P',
        'Camiseta 100% algodao, gola redonda, tamanho P',
        'Malha penteada 30.1, gramatura 160g/m2, encolhimento controlado.',
        39.90, NULL, 3, 'UNIDADE', 'ATIVO', 'Y',
        101044, NULL, 40, 'L2026-077',
        '7896543210043', 2, 50, 1, 0.180, 0.150, 0.150, 300,
        'Linha basica, reposicao continua, sem sazonalidade.',
        NULL, DATE '2026-03-22', DATE '2026-03-22', 'SEED');

INSERT INTO TAB_PRODUTO (PK_ID, DS_NOME, DS_DESCRICAO, DS_OBS_LONGA, VL_PRECO,
                          DT_VALIDADE, FK_CATEGORIA, TP_UNIDADE, TP_STATUS,
                          FL_ATIVO, ID_INTERNO, OBS_INTERNA, NR_SEQ, CD_LOTE,
                          CD_BARRA, NR_PALETE, NR_CAIXA, NR_UNIDADE,
                          VL_PESO_BRUTO, VL_PESO_LIQ, PESO_KG, QTDE_EST,
                          OBS_GERAL, FK_FORNECEDOR, DT_CADASTRO, DT_ALTERACAO, NM_USUARIO_ALT)
VALUES (TAB_PRODUTO_SEQ.NEXTVAL, 'Notebook Ultrafino 14"',
        'Notebook 14 polegadas, SSD 512GB, 16GB RAM',
        'Modelo descontinuado pelo fabricante, vendas somente ate esgotar estoque atual.',
        3299.00, DATE '2027-03-31', 1, 'UNIDADE', 'ATIVO', 'Y',
        101299, 'Sem previsao de reposicao, fabricante descontinuou a linha', 50,
        'L2025-311', '7896543210050', 1, 6, 1, 1.900, 1.600, 1.600, 8,
        'Demo do status Inativo (RB_INATIVO), ainda em estoque, fora de linha.',
        2, DATE '2025-11-05', DATE '2025-11-05', 'SEED');

INSERT INTO TAB_PRODUTO (PK_ID, DS_NOME, DS_DESCRICAO, DS_OBS_LONGA, VL_PRECO,
                          DT_VALIDADE, FK_CATEGORIA, TP_UNIDADE, TP_STATUS,
                          FL_ATIVO, ID_INTERNO, OBS_INTERNA, NR_SEQ, CD_LOTE,
                          CD_BARRA, NR_PALETE, NR_CAIXA, NR_UNIDADE,
                          VL_PESO_BRUTO, VL_PESO_LIQ, PESO_KG, QTDE_EST,
                          OBS_GERAL, FK_FORNECEDOR, DT_CADASTRO, DT_ALTERACAO, NM_USUARIO_ALT)
VALUES (TAB_PRODUTO_SEQ.NEXTVAL, 'Parafusadeira de Bancada',
        'Parafusadeira eletrica de bancada, uso industrial',
        'Recall de seguranca do fabricante em andamento, venda bloqueada ate laudo tecnico.',
        899.00, DATE '2028-01-31', 4, 'CAIXA', 'ATIVO', 'Y',
        101555, 'Aguardando laudo tecnico do fabricante (recall)', 60,
        'L2026-005', '7896543210067', 1, 4, 1, 6.200, 5.800, 5.800, 15,
        'Demo do status Bloqueado (RB_BLOQUEADO), nao liberar venda.',
        1, DATE '2026-01-20', DATE '2026-01-20', 'SEED');

COMMIT;

-- Historico de UPDATE pra aba Auditoria (via TRG_TAB_PRODUTO_AUDIT).
UPDATE TAB_PRODUTO
   SET VL_PRECO = 379.90, DT_ALTERACAO = DATE '2026-04-02', NM_USUARIO_ALT = 'COMPRAS'
 WHERE DS_NOME = 'Furadeira de Impacto 750W';

UPDATE TAB_PRODUTO
   SET TP_STATUS = 'INATIVO', FL_ATIVO = 'N', DT_ALTERACAO = DATE '2026-05-14', NM_USUARIO_ALT = 'COMERCIAL'
 WHERE DS_NOME = 'Notebook Ultrafino 14"';

UPDATE TAB_PRODUTO
   SET TP_STATUS = 'BLOQUEADO', FL_ATIVO = 'N', DT_ALTERACAO = DATE '2026-06-30', NM_USUARIO_ALT = 'QUALIDADE'
 WHERE DS_NOME = 'Parafusadeira de Bancada';

COMMIT;

-- ----------------------------------------------------------------------------
-- Itens do detalhe (BK_ITENS) -- so pra alguns produtos, de proposito.
-- Totais esperados no form: Furadeira 134.90, Fone 29.90, Cafe 17.00,
-- Notebook 209.80, Camiseta 0, Parafusadeira 0.
-- ----------------------------------------------------------------------------
INSERT INTO TAB_PRODUTO_ITEM (FK_PRODUTO_ID, SEQ_ITEM, DS_ITEM, QT_ITEM, VL_UNIT)
SELECT PK_ID, 1, 'Bateria 12V', 1, 89.90
FROM TAB_PRODUTO WHERE DS_NOME = 'Furadeira de Impacto 750W';

INSERT INTO TAB_PRODUTO_ITEM (FK_PRODUTO_ID, SEQ_ITEM, DS_ITEM, QT_ITEM, VL_UNIT)
SELECT PK_ID, 2, 'Carregador rapido', 1, 45.00
FROM TAB_PRODUTO WHERE DS_NOME = 'Furadeira de Impacto 750W';

INSERT INTO TAB_PRODUTO_ITEM (FK_PRODUTO_ID, SEQ_ITEM, DS_ITEM, QT_ITEM, VL_UNIT)
SELECT PK_ID, 1, 'Estojo de transporte', 1, 29.90
FROM TAB_PRODUTO WHERE DS_NOME = 'Fone Bluetooth ANC';

INSERT INTO TAB_PRODUTO_ITEM (FK_PRODUTO_ID, SEQ_ITEM, DS_ITEM, QT_ITEM, VL_UNIT)
SELECT PK_ID, 1, 'Filtro de papel (pacote)', 2, 8.50
FROM TAB_PRODUTO WHERE DS_NOME = 'Cafe Especial Grao 1kg';

INSERT INTO TAB_PRODUTO_ITEM (FK_PRODUTO_ID, SEQ_ITEM, DS_ITEM, QT_ITEM, VL_UNIT)
SELECT PK_ID, 1, 'Mochila para notebook', 1, 129.90
FROM TAB_PRODUTO WHERE DS_NOME = 'Notebook Ultrafino 14"';

INSERT INTO TAB_PRODUTO_ITEM (FK_PRODUTO_ID, SEQ_ITEM, DS_ITEM, QT_ITEM, VL_UNIT)
SELECT PK_ID, 2, 'Mouse sem fio', 1, 79.90
FROM TAB_PRODUTO WHERE DS_NOME = 'Notebook Ultrafino 14"';

COMMIT;

-- ----------------------------------------------------------------------------
-- Conferencia rapida (so leitura): tudo VALID e contagens do seed.
-- ----------------------------------------------------------------------------
SELECT object_type, object_name, status
  FROM user_objects
 WHERE object_name IN ('TAB_CATEGORIA', 'TAB_FORNECEDOR', 'TAB_PRODUTO', 'TAB_PRODUTO_SEQ',
                       'TAB_PRODUTO_ITEM', 'TAB_PRODUTO_AUDIT', 'TAB_FORM_ACESSO',
                       'VW_PRODUTO_RESUMO', 'PKG_PRODUTO', 'TRG_TAB_PRODUTO_AUDIT')
 ORDER BY object_type, object_name;

SELECT 'TAB_PRODUTO' AS tabela, COUNT(*) AS qtd FROM TAB_PRODUTO
UNION ALL SELECT 'TAB_PRODUTO_ITEM',  COUNT(*) FROM TAB_PRODUTO_ITEM
UNION ALL SELECT 'TAB_PRODUTO_AUDIT', COUNT(*) FROM TAB_PRODUTO_AUDIT
UNION ALL SELECT 'TAB_FORNECEDOR',    COUNT(*) FROM TAB_FORNECEDOR
UNION ALL SELECT 'VW_PRODUTO_RESUMO', COUNT(*) FROM VW_PRODUTO_RESUMO;
