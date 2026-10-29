require 'erb'

module Jekyll
  # 금액 → 우아세금·우아대출의 금액별 페이지(가장 가까운 구간)로 연결하는 도우미.
  # wooaapt / wooavilla / wooagongsi 가 같은 파일을 쓴다(수정 시 세 곳 모두 반영).
  # 구간은 우아세금·우아대출이 실제로 만든 금액 페이지와 일치해야 한다(404 방지).
  module TaxLinks
    TAX  = 'https://wooatax.wooahouse.com'
    LOAN = 'https://wooaloan.wooahouse.com'

    # 구간 값은 "억" 단위
    ACQ  = ((2..19).map { |i| i / 2.0 } + [10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5, 15] + (16..30).to_a).uniq.sort
    PROP = ((2..19).map { |i| i / 2.0 } + (10..20).to_a + [25, 30]).uniq.sort
    LOAN_B = [0.1, 0.3, 0.5, 0.7, 1, 1.5, 2, 2.5, 3, 4, 5, 7, 10]

    module_function

    # 구간 값(억) → URL 슬러그. 1.5 → "1억5천", 0.3 → "3천"
    def slug(v)
      eok = v.floor
      cheon = ((v - eok) * 10).round
      s = +''
      s << "#{eok}억" if eok.positive?
      s << "#{cheon}천" if cheon.positive?
      s
    end

    # 구간 값(억) → 사람이 읽는 표기. 1.5 → "1억 5천만원", 5 → "5억원", 0.3 → "3천만원"
    def label(v)
      eok = v.floor
      cheon = ((v - eok) * 10).round
      return "#{cheon}천만원" if eok.zero?
      cheon.zero? ? "#{eok}억원" : "#{eok}억 #{cheon}천만원"
    end

    # 가장 가까운 구간. 구간과 실제 값이 35% 넘게 어긋나면(예: 5천만원 → 1억 구간) 연결하지 않는다.
    def nearest(buckets, eok)
      b = buckets.min_by { |x| [(x - eok).abs, x] }
      ((b - eok).abs / eok) <= 0.35 ? b : nil
    end

    def enc(s)
      ERB::Util.url_encode(s)
    end

    # won: 원 단위 금액
    def property_tax(won)
      return nil unless won && won > 0
      b = nearest(PROP, won / 100_000_000.0)
      return nil unless b
      { 'url' => "#{TAX}/property-tax/#{enc(slug(b))}/", 'label' => label(b) }
    end

    def acquisition(won)
      return nil unless won && won > 0
      b = nearest(ACQ, won / 100_000_000.0)
      return nil unless b
      { 'url' => "#{TAX}/acquisition/#{enc(slug(b))}/", 'label' => label(b) }
    end

    # 매매가의 절반을 빌린다고 가정한 대출 구간
    def loan_half(won)
      return nil unless won && won > 0
      b = nearest(LOAN_B, won / 200_000_000.0)
      return nil unless b
      { 'url' => "#{LOAN}/loan/#{enc(slug(b))}/", 'label' => label(b) }
    end

    # 매매가(만원 단위) → 취득세·대출 링크 묶음
    def for_trade_man(man)
      won = man.to_i * 10_000
      return nil unless won.positive?
      links = { 'acq' => acquisition(won), 'loan' => loan_half(won) }
      links['acq'] || links['loan'] ? links : nil
    end
  end
end
