--[[
zotero_bibliography_docx.lua — filtro companheiro ao zotero.lua

Por que existe: o filtro oficial do Better BibTeX (zotero.lua) converte
citações [@key] em campos vivos do Word, mas o marcador de bibliografia
(``ZOTERO_BIBL CSL_BIBLIOGRAPHY``) ele só emite para ODT. Para DOCX,
o usuário precisava abrir o Word e clicar "Add/Edit Bibliography" manualmente.
Aqui preenchemos essa lacuna: quando o markdown tem
::: {#refs}
:::
emitimos o campo de bibliografia no formato OOXML que o plugin do Zotero
reconhece. No primeiro "Refresh" no Word a bibliografia se materializa
automaticamente, sem clique extra.

Ordem: deve rodar DEPOIS de zotero.lua (o pandoc aplica --lua-filter na ordem
da CLI).
]]--

local function bib_field_xml()
  -- Settings JSON idênticos ao que o plugin Word grava ao inserir uma
  -- bibliografia nova. Zotero re-lê o estado completo via custom XML props
  -- do documento, então isso é suficiente para o Refresh popular tudo.
  local settings = '{"uncited":[],"omitted":[],"custom":[]}'
  return table.concat({
    '<w:p>',
      '<w:r><w:fldChar w:fldCharType="begin"/></w:r>',
      '<w:r><w:instrText xml:space="preserve"> ADDIN ZOTERO_BIBL ',
        settings, ' CSL_BIBLIOGRAPHY </w:instrText></w:r>',
      '<w:r><w:fldChar w:fldCharType="separate"/></w:r>',
      '<w:r><w:t>&lt;Do Zotero Refresh to materialize bibliography&gt;</w:t></w:r>',
      '<w:r><w:fldChar w:fldCharType="end"/></w:r>',
    '</w:p>',
  })
end

function Div(div)
  if FORMAT ~= 'docx' then return nil end
  if not div.attr or div.attr.identifier ~= 'refs' then return nil end
  return pandoc.RawBlock('openxml', bib_field_xml())
end
