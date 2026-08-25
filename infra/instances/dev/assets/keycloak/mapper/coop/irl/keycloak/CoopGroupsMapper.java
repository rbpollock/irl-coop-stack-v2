package coop.irl.keycloak;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

import org.jboss.logging.Logger;
import org.keycloak.models.ClientSessionContext;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.ProtocolMapperModel;
import org.keycloak.models.UserSessionModel;
import org.keycloak.protocol.oidc.mappers.AbstractOIDCProtocolMapper;
import org.keycloak.protocol.oidc.mappers.OIDCAccessTokenMapper;
import org.keycloak.protocol.oidc.mappers.OIDCAttributeMapperHelper;
import org.keycloak.protocol.oidc.mappers.OIDCIDTokenMapper;
import org.keycloak.protocol.oidc.mappers.TokenIntrospectionTokenMapper;
import org.keycloak.protocol.oidc.mappers.UserInfoTokenMapper;
import org.keycloak.provider.ProviderConfigProperty;
import org.keycloak.representations.IDToken;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * coop groups protocol mapper — makes the `groups` scope real.
 *
 * Instead of Keycloak's built-in group model, this mapper resolves a user's
 * RELATED GROUPS live from coop-api (the source of truth for the coop group
 * model) and emits their ids as the `groups` claim. On every token mint it
 * GETs {api_url}?sub=<subject> with a shared bearer token. coop-api stays
 * authoritative; Keycloak fetches on demand (Path A).
 *
 * Config:
 *   api_url   — e.g. http://172.17.0.1:3001/api/internal/groups
 *   api_token — shared bearer secret coop-api expects (Authorization header)
 *
 * A lookup failure never blocks token issuance (groups are best-effort).
 */
public class CoopGroupsMapper extends AbstractOIDCProtocolMapper
        implements OIDCAccessTokenMapper, OIDCIDTokenMapper, UserInfoTokenMapper, TokenIntrospectionTokenMapper {

    public static final String PROVIDER_ID = "oidc-coop-groups-mapper";
    public static final String CLAIM_NAME = "groups";

    private static final String CFG_API_URL = "api_url";
    private static final String CFG_API_TOKEN = "api_token";

    private static final Logger LOG = Logger.getLogger(CoopGroupsMapper.class);

    private static final ObjectMapper JSON = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();

    private static final List<ProviderConfigProperty> CONFIG_PROPERTIES = new ArrayList<>();

    static {
        ProviderConfigProperty url = new ProviderConfigProperty();
        url.setName(CFG_API_URL);
        url.setLabel("coop-api groups URL");
        url.setHelpText("coop-api endpoint returning {\"groups\":[...]} for a subject, e.g. http://172.17.0.1:3001/api/internal/groups");
        url.setType(ProviderConfigProperty.STRING_TYPE);
        CONFIG_PROPERTIES.add(url);

        ProviderConfigProperty token = new ProviderConfigProperty();
        token.setName(CFG_API_TOKEN);
        token.setLabel("Bearer token");
        token.setHelpText("Shared secret coop-api expects in the Authorization header.");
        token.setType(ProviderConfigProperty.PASSWORD);
        CONFIG_PROPERTIES.add(token);

        OIDCAttributeMapperHelper.addIncludeInTokensConfig(CONFIG_PROPERTIES, CoopGroupsMapper.class);
    }

    @Override
    public String getDisplayCategory() {
        return TOKEN_MAPPER_CATEGORY;
    }

    @Override
    public String getDisplayType() {
        return "coop groups (coop-api)";
    }

    @Override
    public String getId() {
        return PROVIDER_ID;
    }

    @Override
    public String getHelpText() {
        return "Resolves the user's related groups live from coop-api (their 1-of-1 group + seats) and emits their ids as the `groups` claim.";
    }

    @Override
    public List<ProviderConfigProperty> getConfigProperties() {
        return CONFIG_PROPERTIES;
    }

    @Override
    protected void setClaim(IDToken token, ProtocolMapperModel mappingModel, UserSessionModel userSession,
                            KeycloakSession session, ClientSessionContext clientSessionCtx) {
        String sub = userSession.getUser().getId();
        String url = mappingModel.getConfig() == null ? null : mappingModel.getConfig().get(CFG_API_URL);
        String bearer = mappingModel.getConfig() == null ? null : mappingModel.getConfig().get(CFG_API_TOKEN);
        if (url == null || url.isEmpty()) {
            return;
        }
        try {
            List<String> groups = fetchGroups(url, bearer, sub);
            if (groups != null) {
                token.getOtherClaims().put(CLAIM_NAME, groups);
            }
        } catch (Exception e) {
            LOG.warnf("coop groups mapper: lookup failed for sub=%s: %s", sub, e.getMessage());
        }
    }

    private List<String> fetchGroups(String url, String bearer, String sub) throws Exception {
        String sep = url.contains("?") ? "&" : "?";
        String target = url + sep + "sub=" + URLEncoder.encode(sub, StandardCharsets.UTF_8);

        HttpRequest.Builder rb = HttpRequest.newBuilder()
                .uri(URI.create(target))
                .timeout(Duration.ofSeconds(5))
                .GET();
        if (bearer != null && !bearer.isEmpty()) {
            rb.header("Authorization", "Bearer " + bearer);
        }
        HttpResponse<String> resp = HTTP.send(rb.build(), HttpResponse.BodyHandlers.ofString());
        if (resp.statusCode() != 200) {
            LOG.warnf("coop groups mapper: coop-api returned HTTP %d for sub=%s", resp.statusCode(), sub);
            return null;
        }
        JsonNode root = JSON.readTree(resp.body());
        JsonNode groupsNode = root.get("groups");
        if (groupsNode == null || !groupsNode.isArray()) {
            return null;
        }
        List<String> out = new ArrayList<>();
        for (JsonNode g : groupsNode) {
            out.add(g.asText());
        }
        return out;
    }
}
