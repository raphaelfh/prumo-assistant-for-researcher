--[[
zotero_live_docx.lua — pré-renderiza citações via --citeproc e embrulha
em campos do Word reconhecidos pelo plugin Zotero, produzindo um docx
indistinguível do que o plugin gera quando o autor insere as citações
manualmente. Roda APÓS --citeproc na cadeia de filtros do pandoc.

Por que existe:
- O zotero.lua oficial do Better BibTeX NÃO chama citeproc; deixa o
  display dos campos como `<Do Zotero Refresh: [@key]>` e exige Refresh
  no Word para formatar. Para um docx final pronto para entrega
  (submissão CEP, paper draft) isso é inaceitável.
- Aqui o pandoc roda citeproc primeiro: o `cite.content` já vem
  formatado (`(Razavi-Shearer et al., 2023)`). Embrulhamos esse texto
  no campo OOXML com a JSON CSL_CITATION ao lado, e o Refresh do Word
  fica no-op (ou re-formata com o mesmo resultado se o usuário trocar
  o CSL).
- Também setamos `meta.ZOTERO_PREF_1` / `ZOTERO_PREF_2` que o pandoc
  serializa em `docProps/custom.xml` como custom doc properties. O
  plugin Word lê o estilo CSL dali e NÃO abre mais o diálogo
  "Document Preferences" no primeiro Refresh.

Pré-requisitos:
- Pandoc 3.0+ (para `pandoc.json`).
- O comando do pandoc precisa ter `--citeproc --bibliography=refs.bib
  --csl=<style>.csl` ANTES de `--lua-filter=zotero_live_docx.lua`.
- `meta.zotero_lookup_file` aponta para JSON `{citekey: {itemID, uri}}`
  fornecido pelo export.py após query no BBT JSON-RPC. Sem isso, os
  campos ainda funcionam mas sem URI para o plugin Word relinkar com
  a biblioteca do Zotero.
- `meta.zotero_csl_style` carrega o nome curto do estilo (ex. "apa").

Limitação conhecida: o display text de cada citação é texto puro
(via `stringify`); itálicos/negritos do CSL são perdidos no display
mas preservados no JSON e re-renderizados ao Refresh no Word.
]]--

local json = pandoc.json

local zotero_lookup = {}
local csl_style_id = 'apa'
local citation_counter = 0
local references_by_key = {}

local function xmlescape(s)
  return (tostring(s)
    :gsub('&', '&amp;')
    :gsub('<', '&lt;')
    :gsub('>', '&gt;')
    :gsub('"', '&quot;')
    :gsub("'", '&apos;'))
end

local function next_citation_id()
  citation_counter = citation_counter + 1
  return string.format('%08d', citation_counter)
end

local function load_lookup_file(path)
  local f = io.open(path, 'r')
  if not f then return end
  local content = f:read('*a')
  f:close()
  local ok, parsed = pcall(json.decode, content)
  if ok and type(parsed) == 'table' then
    for k, v in pairs(parsed) do
      zotero_lookup[k] = v
    end
  end
end

local function zotero_pref_xml()
  -- Mínimo que o plugin Word precisa pra reconhecer o documento como
  -- "Zotero-managed" e pular o diálogo Document Preferences no Refresh.
  -- fieldType=Field é o tipo nativo do .docx (não ReferenceMark, que é
  -- do LibreOffice/ODT). noteType=0 = in-text citations (não footnotes).
  return string.format(
    '<data data-version="3" zotero-version="prumo-assist">'
    .. '<session id="prumo-export"/>'
    .. '<style id="http://www.zotero.org/styles/%s" hasBibliography="1" '
    .. 'bibliographyStyleHasBeenSet="1"/>'
    .. '<prefs><pref name="fieldType" value="Field"/>'
    .. '<pref name="automaticJournalAbbreviations" value="false"/>'
    .. '<pref name="noteType" value="0"/></prefs></data>',
    csl_style_id
  )
end

local function build_csl_citation(cite)
  local plain_text = pandoc.utils.stringify(cite.content)
  local items = {}
  for _, c in ipairs(cite.citations) do
    local key = c.id
    local lookup = zotero_lookup[key] or {}
    local item = { id = lookup.itemID or key }
    if lookup.uri then item.uris = { lookup.uri } end
    if references_by_key[key] then
      item.itemData = references_by_key[key]
    end
    if c.mode == 'SuppressAuthor' then
      item['suppress-author'] = true
    end
    if c.prefix and #c.prefix > 0 then
      item.prefix = pandoc.utils.stringify(c.prefix)
    end
    if c.suffix and #c.suffix > 0 then
      item.suffix = pandoc.utils.stringify(c.suffix)
    end
    table.insert(items, item)
  end
  return {
    citationID = next_citation_id(),
    properties = {
      formattedCitation = plain_text,
      plainCitation = plain_text,
      noteIndex = 0,
    },
    citationItems = items,
    schema = 'https://github.com/citation-style-language/schema/raw/master/csl-citation.json',
  }
end

local function wrap_cite_in_field(cite)
  local csl = build_csl_citation(cite)
  local instr = ' ADDIN ZOTERO_ITEM CSL_CITATION '
              .. xmlescape(json.encode(csl)) .. '   '
  local display_text = xmlescape(pandoc.utils.stringify(cite.content))
  local field = table.concat({
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>',
    '<w:r><w:instrText xml:space="preserve">', instr, '</w:instrText></w:r>',
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>',
    '<w:r><w:rPr><w:noProof/></w:rPr><w:t xml:space="preserve">',
    display_text,
    '</w:t></w:r>',
    '<w:r><w:fldChar w:fldCharType="end"/></w:r>',
  })
  return pandoc.RawInline('openxml', field)
end

local function wrap_bibliography(div)
  -- Campo ZOTERO_BIBL spanando múltiplos parágrafos: <fldChar begin> e
  -- <instrText> ficam num parágrafo dedicado antes da bibliografia
  -- renderizada; <fldChar end> num parágrafo dedicado depois. O Word
  -- aceita campos cruzando parágrafos quando os fldChar match.
  local settings = '{"uncited":[],"omitted":[],"custom":[]}'
  local instr = ' ADDIN ZOTERO_BIBL ' .. settings .. ' CSL_BIBLIOGRAPHY '
  local begin_field = pandoc.RawBlock('openxml', table.concat({
    '<w:p>',
      '<w:r><w:fldChar w:fldCharType="begin"/></w:r>',
      '<w:r><w:instrText xml:space="preserve">', instr, '</w:instrText></w:r>',
      '<w:r><w:fldChar w:fldCharType="separate"/></w:r>',
    '</w:p>',
  }))
  local end_field = pandoc.RawBlock('openxml',
    '<w:p><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
  )
  local blocks = pandoc.List({ begin_field })
  blocks:extend(div.content)
  blocks:insert(end_field)
  return blocks
end

function Pandoc(doc)
  if FORMAT ~= 'docx' then return nil end

  if doc.meta.zotero_lookup_file then
    load_lookup_file(pandoc.utils.stringify(doc.meta.zotero_lookup_file))
  end
  if doc.meta.zotero_csl_style then
    csl_style_id = pandoc.utils.stringify(doc.meta.zotero_csl_style)
  end

  -- pandoc.utils.references(doc) devolve a lista CSL JSON que o citeproc
  -- carregou da bib — usamos para popular itemData de cada citationItem
  -- quando não temos URI do Zotero.
  for _, ref in ipairs(pandoc.utils.references(doc)) do
    references_by_key[ref.id] = ref
  end

  doc.blocks = doc.blocks:walk({
    Cite = wrap_cite_in_field,
    Div = function(div)
      if div.attr and div.attr.identifier == 'refs' then
        return wrap_bibliography(div)
      end
      return nil
    end,
  })

  doc.meta.ZOTERO_PREF_1 = pandoc.MetaInlines({ pandoc.Str(zotero_pref_xml()) })
  doc.meta.ZOTERO_PREF_2 = pandoc.MetaInlines({ pandoc.Str('') })

  return doc
end
