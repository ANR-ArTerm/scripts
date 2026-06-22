<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="xs tei" version="2.0">
    <xsl:output method="xml" encoding="UTF-8" indent="no" omit-xml-declaration="no"/>
    <!--  ============================================================
       VARIABLES GLOBALES
  ============================================================  -->
    <xsl:variable name="UC" select="'ABCDEFGHIJKLMNOPQRSTUVWXYZÀÂÄÉÈÊËÎÏÔÙÛÜ'"/>
    <xsl:variable name="LC" select="'abcdefghijklmnopqrstuvwxyzàâäéèêëîïôùûü'"/>
    <!--  Chiffres romains : corps en majuscules + suffixe ordinal optionnel
       en minuscules (e, è, er, ème, ième)  -->
    <xsl:variable name="ROMAN" select="'^(M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3}))(e|è|er|ème|ieme|ième)?$'"/>
    <!--  Regex qui capture un mot commençant par une majuscule,
       suivi de minuscules ou d'autres majuscules (gère MOTSENCAPS aussi)  -->
    <xsl:variable name="MOT_MAJUSCULE" select="'[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ][A-Za-zÀÂÄÉÈÊËÎÏÔÙÛÜàâäéèêëîïôùûü]*'"/>  <!--  ============================================================
       RÈGLE IDENTITÉ
  ============================================================  -->
    <xsl:template match="@* | node()">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
    </xsl:template>
    <!--  ============================================================
       TEIHEADER : les nœuds texte sont recopiés sans modification.
       La descente continue normalement pour atteindre
       sourceDesc et profileDesc.
       Fonctionne avec ou sans namespace grâce à local-name().
  ============================================================  -->
    <xsl:template match="*[local-name() = 'teiHeader']//text()">
        <xsl:value-of select="."/>
    </xsl:template>
    <!--  ============================================================
       SOURCEDESC : ajout de xi:include IndexOeuvres
  ============================================================  -->
    <xsl:template match="*[local-name() = 'sourceDesc']">
        <xsl:copy>
            <xsl:apply-templates select="@*"/>
            <xsl:apply-templates select="node()[ not(local-name() = 'include' and contains(@href, 'IndexOeuvres')) ][ not(local-name() = 'listObject') ]"/>
            <xsl:text> </xsl:text>
            <xsl:text disable-output-escaping="yes">&lt;xi:include href="../IndexOeuvres.xml" xpointer="element(/1/1)"/&gt;</xsl:text>
        </xsl:copy>
    </xsl:template>
    <!--  ============================================================
       PROFILEDESC : reconstruction avec xi:include
  ============================================================  -->
    <xsl:template match="*[local-name() = 'profileDesc']">
        <xsl:copy>
            <xsl:text disable-output-escaping="yes">&lt;xi:include href="../IndexPersonnes.xml" xpointer="element(/1/1)"/&gt;</xsl:text>
            <xsl:text> </xsl:text>
            <xsl:text disable-output-escaping="yes">&lt;xi:include href="../IndexLieux.xml" xpointer="element(/1/1)"/&gt;</xsl:text>
        </xsl:copy>
    </xsl:template>
    <!--  ============================================================
       BALISES PROTÉGÉES DANS LE BODY
  ============================================================  -->
    <xsl:template match="*[local-name() = 'persName' or local-name() = 'placeName' or local-name() = 'objectName' or local-name() = 'date' or (local-name() = 'hi' and @rend = 'capitals') or local-name() = 'item']">
        <xsl:copy>
            <xsl:apply-templates select="@*"/>
            <xsl:value-of select="."/>
        </xsl:copy>
    </xsl:template>
    <!--  ============================================================
       NŒUDS TEXTE CIBLES : dans <p> et <l>, hors balises protégées
       et hors teiHeader.
  ============================================================  -->
    <xsl:template match=" text()[ (ancestor::*[local-name()='p'] or ancestor::*[local-name()='l']) and not(ancestor::*[local-name()='teiHeader']) and not(ancestor::*[local-name()='persName'] or ancestor::*[local-name()='placeName'] or ancestor::*[local-name()='objectName'] or ancestor::*[local-name()='date'] or ancestor::*[local-name()='hi' and @rend='capitals']) ]">
        <xsl:variable name="ancetre_cible" select="(ancestor::*[local-name()='p'] | ancestor::*[local-name()='l'])[last()]"/>
        <!--  Ce nœud texte est-il le premier nœud texte significatif
         du <p>/<l> ancêtre ? Si oui, sa première lettre non-espace
         marque le début de la balise → à conserver.  -->
        <xsl:variable name="est_debut_balise" as="xs:boolean" select="not( current()/preceding::text()[ ancestor::*[. is $ancetre_cible] ][ not(ancestor::*[local-name()='persName'] or ancestor::*[local-name()='placeName'] or ancestor::*[local-name()='objectName'] or ancestor::*[local-name()='date'] or ancestor::*[local-name()='hi' and @rend='capitals']) and normalize-space(.) != '' ] )"/>
        <xsl:call-template name="traiter_texte">
            <xsl:with-param name="texte" select="string(.)"/>
            <xsl:with-param name="est_debut" select="$est_debut_balise"/>
        </xsl:call-template>
    </xsl:template>
    <!--  ============================================================
       TRAITEMENT DU TEXTE PAR TOKENISATION (analyze-string)
       Découpe le texte en alternant : mots à majuscule initiale / reste.
       Aucune récursion par caractère → pas de risque de stack overflow,
       même sur des paragraphes de plusieurs milliers de caractères.
  ============================================================  -->
    <xsl:template name="traiter_texte">
        <xsl:param name="texte" as="xs:string"/>
        <xsl:param name="est_debut" as="xs:boolean"/>
        <!--  Position du premier caractère non-espace, pour gérer
         un éventuel espace avant la majuscule de début de balise  -->
        <xsl:variable name="premiere_pos_utile" as="xs:integer" select="string-length($texte) - string-length(replace($texte, '^\s+', '')) + 1"/>
        <xsl:analyze-string select="$texte" regex="{$MOT_MAJUSCULE}">
            <xsl:matching-substring>
                <xsl:variable name="mot" select="."/>
                <xsl:variable name="pos_dans_texte" select="string-length(substring-before($texte, $mot)) + 1"/>
                <!--  Texte précédant ce mot dans la chaîne complète (contexte gauche)  -->
                <xsl:variable name="gauche" select="substring($texte, 1, $pos_dans_texte - 1)"/>
                <xsl:variable name="conserver" as="xs:boolean">
                    <xsl:choose>
                        <!--  Règle 1 : chiffre romain  -->
                        <xsl:when test="matches($mot, $ROMAN)">
                            <xsl:value-of select="true()"/>
                        </xsl:when>
                        <!--  Règle 2 : première lettre du <p>/<l>, espaces initiaux ignorés  -->
                        <xsl:when test="$est_debut and $pos_dans_texte = $premiere_pos_utile">
                            <xsl:value-of select="true()"/>
                        </xsl:when>
                        <!--  Règle 3 : précédé d'une ponctuation forte + espaces  -->
                        <xsl:when test="matches($gauche, '[.!?]\s*$')">
                            <xsl:value-of select="true()"/>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="false()"/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:variable>
                <xsl:choose>
                    <xsl:when test="$conserver">
                        <xsl:value-of select="$mot"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <!--  Mise en minuscule directe de la première lettre uniquement  -->
                        <xsl:value-of select="concat(translate(substring($mot,1,1), $UC, $LC), substring($mot, 2))"/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:matching-substring>
            <xsl:non-matching-substring>
                <xsl:value-of select="."/>
            </xsl:non-matching-substring>
        </xsl:analyze-string>
    </xsl:template>
</xsl:stylesheet>