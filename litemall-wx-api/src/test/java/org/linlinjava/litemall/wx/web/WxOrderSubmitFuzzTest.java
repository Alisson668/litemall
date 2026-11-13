package org.linlinjava.litemall.wx.web;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.linlinjava.litemall.core.config.GlobalExceptionHandler;
import org.linlinjava.litemall.db.domain.LitemallAddress;
import org.linlinjava.litemall.db.domain.LitemallOrder;
import org.linlinjava.litemall.db.service.LitemallAddressService;
import org.linlinjava.litemall.db.service.LitemallCartService;
import org.linlinjava.litemall.db.service.LitemallOrderService;
import org.linlinjava.litemall.wx.annotation.support.LoginUserHandlerMethodArgumentResolver;
import org.linlinjava.litemall.wx.service.UserTokenManager;
import org.linlinjava.litemall.wx.service.WxOrderService;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.MediaType;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.stream.Stream;

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

@DisplayName("/wx/order/submit semantic fuzzing and security")
class WxOrderSubmitFuzzTest {
    private static final String TOKEN_HEADER =
            LoginUserHandlerMethodArgumentResolver.LOGIN_TOKEN_KEY;

    @Mock
    private LitemallAddressService addressService;
    @Mock
    private LitemallCartService cartService;
    @Mock
    private LitemallOrderService orderService;
    @InjectMocks
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

    static Stream<Arguments> invalidPayloads() {
        return Stream.of(
                Arguments.of("missing cartId", "{\"addressId\":2,\"couponId\":0}", 401),
                Arguments.of("missing couponId", "{\"cartId\":1,\"addressId\":2}", 401),
                Arguments.of("null couponId",
                        "{\"cartId\":1,\"addressId\":2,\"couponId\":null}", 401),
                Arguments.of("zero address",
                        "{\"cartId\":1,\"addressId\":0,\"couponId\":0}", 402),
                Arguments.of("negative address",
                        "{\"cartId\":1,\"addressId\":-2,\"couponId\":0}", 402),
                Arguments.of("negative cart",
                        "{\"cartId\":-1,\"addressId\":2,\"couponId\":0}", 402),
                Arguments.of("invalid coupon sentinel",
                        "{\"cartId\":1,\"addressId\":2,\"couponId\":-2}", 402),
                Arguments.of("text integer",
                        "{\"cartId\":\"1\",\"addressId\":\"2\",\"couponId\":0}", 402),
                Arguments.of("boolean integer",
                        "{\"cartId\":true,\"addressId\":2,\"couponId\":0}", 402),
                Arguments.of("array integer",
                        "{\"cartId\":[1],\"addressId\":2,\"couponId\":0}", 402),
                Arguments.of("object integer",
                        "{\"cartId\":{\"value\":1},\"addressId\":2,\"couponId\":0}", 402),
                Arguments.of("integer overflow",
                        "{\"cartId\":1,\"addressId\":2147483648,\"couponId\":0}", 402),
                Arguments.of("decimal integer",
                        "{\"cartId\":1,\"addressId\":2.5,\"couponId\":0}", 402),
                Arguments.of("sql injection",
                        "{\"cartId\":1,\"addressId\":\"2 UNION SELECT 1\",\"couponId\":0}",
                        402),
                Arguments.of("invalid JSON", "{", 402),
                Arguments.of("array root", "[]", 402),
                Arguments.of("non-string message",
                        "{\"cartId\":1,\"addressId\":2,\"couponId\":0,\"message\":123}",
                        402)
        );
    }

    @ParameterizedTest(name = "{0} -> errno {2}")
    @MethodSource("invalidPayloads")
    void rejectsInvalidPayloadWithoutServerError(String caseName, String body, int errno)
            throws Exception {
        String errmsg = errno == 401 ? "参数不对" : "参数值不对";
        mockMvc.perform(authenticatedJson(body))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.errno").value(errno))
                .andExpect(jsonPath("$.errmsg").value(errmsg));
    }

    @Test
    @DisplayName("SQL injection text never reaches the database")
    void sqlInjectionTextNeverReachesDatabase() throws Exception {
        String body =
                "{\"cartId\":1,\"addressId\":\"2 UNION SELECT 1\",\"couponId\":0}";

        mockMvc.perform(authenticatedJson(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(402))
                .andExpect(jsonPath("$.errmsg").value("参数值不对"));

        verifyZeroInteractions(addressService);
    }

    @Test
    @DisplayName("invalid UTF-8 payload is contained as a business error")
    void invalidUtf8PayloadDoesNotCrash() throws Exception {
        byte[] body = new byte[]{'{', (byte) 0xC3, '(', '}'};

        mockMvc.perform(post("/wx/order/submit")
                        .header(TOKEN_HEADER, token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .accept(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(402))
                .andExpect(jsonPath("$.errmsg").value("参数值不对"));
    }

    @Test
    @DisplayName("64 KiB message does not trigger a server crash")
    void oversizedMessageDoesNotCrash() throws Exception {
        char[] chars = new char[65536];
        Arrays.fill(chars, 'x');
        String body = "{\"cartId\":1,\"addressId\":2,\"couponId\":0,\"message\":\""
                + new String(chars) + "\"}";

        mockMvc.perform(authenticatedJson(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(401))
                .andExpect(jsonPath("$.errmsg").value("参数不对"));
    }

    @Test
    @DisplayName("body userId cannot redirect the address lookup")
    void bodyUserIdCannotRedirectAddressLookup() throws Exception {
        String body =
                "{\"userId\":999,\"cartId\":1,\"addressId\":2,\"couponId\":0}";

        mockMvc.perform(authenticatedJson(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(401))
                .andExpect(jsonPath("$.errmsg").value("参数不对"));

        verify(addressService).query(7, 2);
        verify(addressService, never()).query(999, 2);
    }

    @Test
    @DisplayName("cart IDOR is denied using the authenticated userId")
    void cartIdorUsesAuthenticatedUserId() throws Exception {
        when(addressService.query(7, 2)).thenReturn(new LitemallAddress());
        when(cartService.findById(7, 33)).thenReturn(null);
        String body =
                "{\"userId\":999,\"cartId\":33,\"addressId\":2,\"couponId\":0}";

        mockMvc.perform(authenticatedJson(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(402))
                .andExpect(jsonPath("$.errmsg").value("参数值不对"));

        verify(cartService).findById(7, 33);
        verify(cartService, never()).findById(999, 33);
    }

    @Test
    @DisplayName("order detail rejects a mismatched owner")
    void orderDetailRejectsMismatchedOwner() throws Exception {
        LitemallOrder order = new LitemallOrder();
        order.setUserId(999);
        when(orderService.findById(7, 55)).thenReturn(order);

        mockMvc.perform(get("/wx/order/detail")
                        .header(TOKEN_HEADER, token)
                        .param("orderId", "55")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(721))
                .andExpect(jsonPath("$.errmsg").value("不是当前用户的订单"));

        verify(orderService).findById(7, 55);
        verify(orderService, never()).findById(999, 55);
    }

    @Test
    @DisplayName("missing authentication returns 501 before parsing")
    void missingAuthenticationReturnsUnlogin() throws Exception {
        mockMvc.perform(post("/wx/order/submit")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cartId\":1,\"addressId\":2,\"couponId\":0}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errno").value(501))
                .andExpect(jsonPath("$.errmsg").value("请登录"));

        verifyZeroInteractions(addressService, cartService, orderService);
    }

    @Test
    @DisplayName("non-JSON content type is rejected before service execution")
    void nonJsonContentTypeIsRejected() throws Exception {
        mockMvc.perform(post("/wx/order/submit")
                        .header(TOKEN_HEADER, token)
                        .contentType(MediaType.TEXT_PLAIN)
                        .content("{\"cartId\":1,\"addressId\":2,\"couponId\":0}"))
                .andExpect(status().isUnsupportedMediaType())
                .andExpect(jsonPath("$.errno").value(415))
                .andExpect(jsonPath("$.errmsg").value("请求媒体类型不支持"));

        verifyZeroInteractions(addressService, cartService, orderService);
    }

    private MockHttpServletRequestBuilder authenticatedJson(String body) {
        return post("/wx/order/submit")
                .header(TOKEN_HEADER, token)
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.APPLICATION_JSON)
                .content(body.getBytes(StandardCharsets.UTF_8));
    }
}
