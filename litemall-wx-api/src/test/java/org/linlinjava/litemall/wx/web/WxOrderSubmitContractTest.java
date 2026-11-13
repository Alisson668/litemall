package org.linlinjava.litemall.wx.web;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.linlinjava.litemall.core.config.GlobalExceptionHandler;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.wx.annotation.support.LoginUserHandlerMethodArgumentResolver;
import org.linlinjava.litemall.wx.service.UserTokenManager;
import org.linlinjava.litemall.wx.service.WxOrderService;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.MediaType;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.HashMap;
import java.util.Map;

import static org.mockito.Matchers.anyString;
import static org.mockito.Matchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyZeroInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@DisplayName("/wx/order/submit REST contract")
class WxOrderSubmitContractTest {
    private static final String TOKEN_HEADER =
            LoginUserHandlerMethodArgumentResolver.LOGIN_TOKEN_KEY;
    private static final String VALID_BODY =
            "{\"cartId\":1,\"addressId\":2,\"couponId\":0}";

    @Mock
    private WxOrderService wxOrderService;

    private MockMvc mockMvc;
    private String token;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.initMocks(this);
        WxOrderController controller = new WxOrderController();
        ReflectionTestUtils.setField(controller, "wxOrderService", wxOrderService);
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setCustomArgumentResolvers(new LoginUserHandlerMethodArgumentResolver())
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
        token = UserTokenManager.generateToken(7);
    }

    @Test
    @DisplayName("valid JSON is delegated with authenticated userId")
    void delegatesValidRequestWithAuthenticatedUser() throws Exception {
        Map<String, Object> data = new HashMap<>();
        data.put("orderId", 42);
        data.put("payed", false);
        data.put("grouponLinkId", 0);
        when(wxOrderService.submit(eq(7), eq(VALID_BODY)))
                .thenReturn(ResponseUtil.ok(data));

        mockMvc.perform(post("/wx/order/submit")
                        .header(TOKEN_HEADER, token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .accept(MediaType.APPLICATION_JSON)
                        .content(VALID_BODY))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.errno").value(0))
                .andExpect(jsonPath("$.errmsg").value("成功"))
                .andExpect(jsonPath("$.data.orderId").value(42))
                .andExpect(jsonPath("$.data.payed").value(false))
                .andExpect(jsonPath("$.data.grouponLinkId").value(0));

        verify(wxOrderService).submit(7, VALID_BODY);
    }

    @Test
    @DisplayName("body userId cannot override authenticated identity")
    void bodyUserIdCannotOverrideAuthenticatedIdentity() throws Exception {
        String body = "{\"userId\":999,\"cartId\":1,\"addressId\":2,\"couponId\":0}";
        when(wxOrderService.submit(eq(7), eq(body))).thenReturn(ResponseUtil.ok());

        mockMvc.perform(post("/wx/order/submit")
                        .header(TOKEN_HEADER, token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(0))
                .andExpect(jsonPath("$.errmsg").value("成功"));

        verify(wxOrderService).submit(7, body);
        verify(wxOrderService, never()).submit(eq(999), anyString());
    }

    @Test
    @DisplayName("missing token returns business error 501")
    void missingTokenReturnsUnlogin() throws Exception {
        when(wxOrderService.submit(null, VALID_BODY)).thenReturn(ResponseUtil.unlogin());

        mockMvc.perform(post("/wx/order/submit")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_BODY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(501))
                .andExpect(jsonPath("$.errmsg").value("请登录"));

        verify(wxOrderService).submit(null, VALID_BODY);
    }

    @Test
    @DisplayName("invalid JWT is treated as anonymous")
    void invalidTokenIsTreatedAsAnonymous() throws Exception {
        when(wxOrderService.submit(null, VALID_BODY)).thenReturn(ResponseUtil.unlogin());

        mockMvc.perform(post("/wx/order/submit")
                        .header(TOKEN_HEADER, "not-a-jwt")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_BODY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(501))
                .andExpect(jsonPath("$.errmsg").value("请登录"));

        verify(wxOrderService).submit(null, VALID_BODY);
    }

    @Test
    @DisplayName("text/plain is rejected with HTTP 415")
    void rejectsNonJsonContentType() throws Exception {
        mockMvc.perform(post("/wx/order/submit")
                        .header(TOKEN_HEADER, token)
                        .contentType(MediaType.TEXT_PLAIN)
                        .content(VALID_BODY))
                .andExpect(status().isUnsupportedMediaType())
                .andExpect(jsonPath("$.errno").value(415))
                .andExpect(jsonPath("$.errmsg").value("请求媒体类型不支持"));

        verifyZeroInteractions(wxOrderService);
    }

    @Test
    @DisplayName("GET on submit is rejected with HTTP 405")
    void rejectsWrongHttpMethod() throws Exception {
        mockMvc.perform(get("/wx/order/submit")
                        .header(TOKEN_HEADER, token))
                .andExpect(status().isMethodNotAllowed())
                .andExpect(jsonPath("$.errno").value(405))
                .andExpect(jsonPath("$.errmsg").value("请求方法不支持"));

        verifyZeroInteractions(wxOrderService);
    }

    @Test
    @DisplayName("client cannot request an unsupported response media type")
    void rejectsUnsupportedAcceptHeader() throws Exception {
        mockMvc.perform(post("/wx/order/submit")
                        .header(TOKEN_HEADER, token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .accept(MediaType.TEXT_PLAIN)
                        .content(VALID_BODY))
                .andExpect(status().isNotAcceptable())
                .andExpect(content().string(""));

        verifyZeroInteractions(wxOrderService);
    }
}
