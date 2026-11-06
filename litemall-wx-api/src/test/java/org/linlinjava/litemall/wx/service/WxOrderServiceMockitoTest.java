package org.linlinjava.litemall.wx.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.linlinjava.litemall.db.service.LitemallAddressService;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyZeroInteractions;
import static org.mockito.Mockito.when;

@DisplayName("订单提交的 Mockito 交互")
class WxOrderServiceMockitoTest {
    @Mock
    private LitemallAddressService addressService;

    @InjectMocks
    private WxOrderService orderService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.initMocks(this);
    }

    @Test
    @DisplayName("未登录时直接返回 501")
    void rejectsAnonymousSubmission() {
        @SuppressWarnings("unchecked")
        Map<String, Object> response = (Map<String, Object>) orderService.submit(null, "{}");

        assertAll(
                () -> assertEquals(501, response.get("errno")),
                () -> verifyZeroInteractions(addressService));
    }

    @Test
    @DisplayName("缺少地址时查询后返回 401")
    void rejectsMissingAddress() {
        when(addressService.query(7, 22)).thenReturn(null);

        @SuppressWarnings("unchecked")
        Map<String, Object> response = (Map<String, Object>) orderService.submit(
                7, "{\"cartId\":0,\"addressId\":22,\"couponId\":0}");

        assertAll(
                () -> assertEquals(401, response.get("errno")),
                () -> verify(addressService).query(7, 22));
    }
}
