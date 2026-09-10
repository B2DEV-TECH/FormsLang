-- ============================================================================
-- Schema de apoio para tests/fixtures/minicase/module.xml (MINI_PRODUTO)
--
-- Cria tudo que o form espera encontrar no schema FORMSLANG -- mesmo schema do
-- apex_username em config.json -- pra compilar e rodar de verdade no Forms
-- Builder. 100% sintetico, sem dado de cliente.
--
-- Sao dois objetos, e so. Comparado ao demo_schema.sql do showcase (10
-- objetos, 4 tabelas de apoio, package, view e trigger de auditoria), aqui
-- nao ha lookup, nao ha detalhe, nao ha package: a regra do EAN-13 mora
-- DENTRO do trigger do form, de proposito, pra que a APEX validation
-- exportada importe e rode sem instalar nada alem desta tabela.
--
--   TAB_MINI_PRODUTO      -> bloco unico BK_PRODUTO
--   TAB_MINI_PRODUTO_SEQ  -> PRE-INSERT de BK_PRODUTO
--
-- Nomes proprios (prefixo TAB_MINI_) pra conviver com o schema do showcase
-- no mesmo usuario FORMSLANG sem colidir.
--
-- Como rodar: conectado como SYSTEM (ou qualquer usuario com privilegio de
-- trocar de schema) no FREEPDB1, execute o script inteiro de uma vez no
-- PL/SQL Developer. Se preferir, conecte direto como FORMSLANG e apague a
-- linha ALTER SESSION abaixo. Por SQLcl:
--   sql -S -thin FORMSLANG/<senha>@localhost:1521/FREEPDB1 @mini_schema.sql
-- ============================================================================

ALTER SESSION SET CURRENT_SCHEMA = FORMSLANG;

-- Reset idempotente (ignora "objeto nao existe" -- ORA-00942 tabela,
-- ORA-02289 sequence) pra poder rodar o script de novo.
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE TAB_MINI_PRODUTO';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN
   EXECUTE IMMEDIATE 'DROP SEQUENCE TAB_MINI_PRODUTO_SEQ';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -2289 THEN RAISE; END IF; END;
/

-- ----------------------------------------------------------------------------
-- TAB_MINI_PRODUTO -- a tabela base do bloco BK_PRODUTO.
--
-- Uma coluna por item do form, na mesma ordem em que aparecem na tela. As
-- CHECK constraints deliberadamente NAO repetem as regras dos triggers: a
-- demo mostra a regra saindo do Forms e chegando no APEX como validation, e
-- uma constraint fazendo o mesmo trabalho por baixo confundiria a leitura de
-- onde a rejeicao nasceu. A unica que existe e a de dominio do FL_ATIVO.
-- ----------------------------------------------------------------------------
CREATE TABLE TAB_MINI_PRODUTO (
   PK_ID          NUMBER(10)      NOT NULL,
   DS_NOME        VARCHAR2(100)   NOT NULL,
   CD_BARRA       VARCHAR2(13),
   VL_PRECO       NUMBER(10,2)    NOT NULL,
   VL_PESO_LIQ    NUMBER(10,3),
   VL_PESO_BRUTO  NUMBER(10,3),
   FL_ATIVO       VARCHAR2(1)     DEFAULT 'Y' NOT NULL,
   DT_CADASTRO    DATE            DEFAULT SYSDATE NOT NULL,
   CONSTRAINT PK_TAB_MINI_PRODUTO PRIMARY KEY (PK_ID),
   CONSTRAINT CK_MINI_PRODUTO_ATIVO CHECK (FL_ATIVO IN ('Y', 'N'))
);

COMMENT ON TABLE  TAB_MINI_PRODUTO               IS 'Fixture minicase do FormsLang -- sintetica, sem dado de cliente.';
COMMENT ON COLUMN TAB_MINI_PRODUTO.PK_ID         IS 'Gerado pela sequence no PRE-INSERT do form.';
COMMENT ON COLUMN TAB_MINI_PRODUTO.CD_BARRA      IS 'EAN-13 validado pelo WHEN-VALIDATE-ITEM do form.';
COMMENT ON COLUMN TAB_MINI_PRODUTO.VL_PESO_LIQ   IS 'Nunca maior que VL_PESO_BRUTO -- regra do WHEN-VALIDATE-RECORD.';
COMMENT ON COLUMN TAB_MINI_PRODUTO.DT_CADASTRO   IS 'Carimbado pelo PRE-INSERT do form.';

CREATE SEQUENCE TAB_MINI_PRODUTO_SEQ START WITH 100 INCREMENT BY 1 NOCACHE;

-- ----------------------------------------------------------------------------
-- Seed: quatro produtos ativos e um inativo.
--
-- O inativo existe pra que o PRE-QUERY tenha o que filtrar: sem ele, o
-- DEFAULT_WHERE "FL_ATIVO = 'Y'" nao muda nada e a demo nao prova que o
-- filtro esta ativo. Todos os EAN-13 sao validos pelo algoritmo do trigger
-- (soma ponderada 1/3, digito verificador = MOD(10 - MOD(soma,10), 10)) --
-- se algum estivesse errado, o form recusaria seu proprio seed.
-- ----------------------------------------------------------------------------
INSERT INTO TAB_MINI_PRODUTO (PK_ID, DS_NOME, CD_BARRA, VL_PRECO, VL_PESO_LIQ, VL_PESO_BRUTO, FL_ATIVO)
VALUES (TAB_MINI_PRODUTO_SEQ.NEXTVAL, 'Furadeira de Impacto 650W', '7891234567895', 289.90, 2.400, 2.850, 'Y');

INSERT INTO TAB_MINI_PRODUTO (PK_ID, DS_NOME, CD_BARRA, VL_PRECO, VL_PESO_LIQ, VL_PESO_BRUTO, FL_ATIVO)
VALUES (TAB_MINI_PRODUTO_SEQ.NEXTVAL, 'Notebook Ultrafino 14"', '7891000000120', 4199.00, 1.240, 1.680, 'Y');

INSERT INTO TAB_MINI_PRODUTO (PK_ID, DS_NOME, CD_BARRA, VL_PRECO, VL_PESO_LIQ, VL_PESO_BRUTO, FL_ATIVO)
VALUES (TAB_MINI_PRODUTO_SEQ.NEXTVAL, 'Camiseta Algodao M', '7892000000349', 59.90, 0.180, 0.220, 'Y');

INSERT INTO TAB_MINI_PRODUTO (PK_ID, DS_NOME, CD_BARRA, VL_PRECO, VL_PESO_LIQ, VL_PESO_BRUTO, FL_ATIVO)
VALUES (TAB_MINI_PRODUTO_SEQ.NEXTVAL, 'Parafusadeira 12V', '7893000000568', 349.90, 1.050, 1.400, 'Y');

-- O inativo: nao aparece na consulta do form enquanto o PRE-QUERY estiver la.
INSERT INTO TAB_MINI_PRODUTO (PK_ID, DS_NOME, CD_BARRA, VL_PRECO, VL_PESO_LIQ, VL_PESO_BRUTO, FL_ATIVO)
VALUES (TAB_MINI_PRODUTO_SEQ.NEXTVAL, 'Trena Descontinuada 5m', '7894000000787', 19.90, 0.150, 0.190, 'N');

COMMIT;

-- ----------------------------------------------------------------------------
-- Conferencia rapida (so leitura): objetos VALID, o seed inteiro e o
-- recorte que o form vai enxergar depois do DEFAULT_WHERE do PRE-QUERY.
-- ----------------------------------------------------------------------------
SELECT object_type, object_name, status
  FROM user_objects
 WHERE object_name IN ('TAB_MINI_PRODUTO', 'TAB_MINI_PRODUTO_SEQ')
 ORDER BY object_type, object_name;

SELECT 'seed completo'         AS recorte, COUNT(*) AS qtd FROM TAB_MINI_PRODUTO
UNION ALL
SELECT 'visivel no form (Y)',  COUNT(*) FROM TAB_MINI_PRODUTO WHERE FL_ATIVO = 'Y';
